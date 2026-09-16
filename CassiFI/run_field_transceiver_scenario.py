"""Exercise field-owned transceivers against common tasks and unreduced dynamics.

All owners and evidence are isolated. The controlled observations describe two
linear instruments, not recordings from a biological or physical nervous system.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
import platform
from typing import Any, Mapping

import numpy as np
import torch

from cassi_field_atlas import (
    AtlasState, FieldIntelligenceError, Guard, RelationChart, VariableSpec,
    canonical_json_bytes, sha256_value,
)
from cassi_field_owner import AuthorityGrant, FieldIntelligenceOwner, SourceInput
from cassi_field_transceiver import (
    advance_transceiver, condense_workspace, inspect_transceiver, reset_transceiver,
)
from cassi_resonant_field import ResonantNumericalError, ResonantProfile, initial_workspace

CONTEXT = {"mechanism": "connected"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def learn_instrument(owner: FieldIntelligenceOwner, name: str, gain: float) -> list[str]:
    for variable in (
        VariableSpec(f"{name}:bias", kind="constant", constant=1.0),
        VariableSpec(f"{name}:input", lower=-40.0, upper=40.0),
        VariableSpec(f"{name}:output", lower=-40.0, upper=40.0),
    ):
        owner.configure_variable(f"configure:{variable.variable_id}", variable)
    owner.configure_chart(
        f"configure:{name}:chart",
        RelationChart.empty(
            chart_id=name, scope=(f"{name}:bias", f"{name}:input", f"{name}:output"),
            ridge=0.01, prior_mass=1e-4, observation_norm_bound=100.0,
            guards=(Guard("mechanism", "eq", "connected"),),
        ),
    )
    revisions = []
    for index, value in enumerate((-3.0, -2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 3.0)):
        values = {f"{name}:bias": 1.0, f"{name}:input": value, f"{name}:output": gain * value}
        source = SourceInput(
            source_id=f"instrument:{name}:{index}", content=canonical_json_bytes(values),
            media_type="application/json", codec="utf-8", observed_timestamp=str(index),
            scope="transceiver-scenario", claim_category="controlled-measurement",
            fidelity="exact-record", labels=("transceiver-scenario",),
        )
        result = owner.admit_observation(
            operation_id=f"learn:{name}:{index}", source=source, values=values,
            context=CONTEXT, target_chart_ids=(name,),
        )
        revisions.append(result["source"]["revision_id"])
    return revisions


def condense(owner: FieldIntelligenceOwner, name: str, *, rank: int = 16) -> Mapping[str, Any]:
    return owner.condense_transceiver(
        f"condense:{name}", transceiver_id=name, chart_ids=(name,),
        input_ids=(f"{name}:input",), output_ids=(f"{name}:output",), context=CONTEXT,
        rank=rank, error_allowance=1e-3, input_bound=4.0, horizon_ticks=128,
    )["receipt"]


def trace(kernel: Mapping[str, Any], name: str, inputs: list[float], *, full: bool = False) -> Mapping[str, Any]:
    state = reset_transceiver(kernel)
    values, bounds = [], []
    full_steps = reduced_steps = applications = 0
    started = perf_counter()
    for value in inputs:
        state, receipt = advance_transceiver(
            kernel, state, inputs={f"{name}:input": value}, force_full=full,
        )
        values.append(float(receipt["values"][f"{name}:output"]))
        bounds.append(float(receipt["error_bound"]))
        counts = receipt.get("counts", {})
        full_steps += int(counts.get("full_steps", 0))
        reduced_steps += int(counts.get("reduced_steps", 0))
        applications += int(counts.get("operator_applications", 0))
    return {
        "values": values, "bounds": bounds, "state": state,
        "elapsed_seconds": perf_counter() - started,
        "full_steps": full_steps, "reduced_steps": reduced_steps,
        "operator_applications": applications,
    }


def numerical_scenario(home: Path, *, beta: float) -> Mapping[str, Any]:
    initial = AtlasState(resonant_workspace=initial_workspace(ResonantProfile(beta=beta, damping=0.5)))
    with FieldIntelligenceOwner(home, initial_state=initial) as owner:
        learn_instrument(owner, "gain", 2.0)
        memory = canonical_json_bytes([chart.as_dict() for chart in owner.state.charts])
        evidence_tick = owner.state.logical_tick
        build = condense(owner, "gain")
        kernel = owner.state.transceiver("gain").kernel
        require(kernel is not None, "condensation lost its realization")
        stimuli = [0.25] * 4 + [0.0] * 4 + [-0.75] * 4 + [1.25] * 4 + [0.0] * 16
        compact = trace(kernel, "gain", stimuli)
        full = trace(kernel, "gain", stimuli, full=True)
        errors = np.abs(np.asarray(compact["values"]) - full["values"])
        allowances = np.asarray(compact["bounds"]) + np.asarray(full["bounds"]) + 1e-8
        require(bool(np.all(errors <= allowances)), "transceiver trajectory escaped its declared error bound")
        replay = trace(kernel, "gain", stimuli)
        require(canonical_json_bytes(compact["state"]) == canonical_json_bytes(replay["state"]), "numeric replay changed temporal state")
        reverse = trace(kernel, "gain", list(reversed(stimuli)))
        order_difference = abs(compact["values"][-1] - reverse["values"][-1])
        require(order_difference > 1e-5, "transceiver discarded the order of equal-content input histories")
        sustained = trace(kernel, "gain", [1.75] * 192)
        held_out_error = abs(sustained["values"][-1] - 3.5)
        require(held_out_error < 0.02, "transceiver did not recover the held-out learned instrument response")
        require(memory == canonical_json_bytes([chart.as_dict() for chart in owner.state.charts]), "transceiver execution changed admitted memory")
        require(owner.state.logical_tick == evidence_tick, "transceiver execution consumed evidence again")
        if beta == 0.0:
            require(compact["reduced_steps"] > 0, "linear transceiver did not execute a genuinely compact path")
        return {
            "beta": beta, "build": build, "dimensions": kernel["dimensions"],
            "maximum_trajectory_error": float(errors.max()), "maximum_claimed_bound": max(compact["bounds"]),
            "order_difference": order_difference, "held_out_prediction": sustained["values"][-1],
            "held_out_target": 3.5, "held_out_absolute_error": held_out_error,
            "compact": {key: value for key, value in compact.items() if key != "state"},
            "full": {key: value for key, value in full.items() if key != "state"},
            "exact_numeric_replay": True, "learned_memory_unchanged": True,
            "evidence_clock_unchanged": True,
        }


def owner_scenario(home: Path) -> Mapping[str, Any]:
    initial = AtlasState(resonant_workspace=initial_workspace(ResonantProfile(beta=0.0, damping=0.5)))
    owner = FieldIntelligenceOwner(home, initial_state=initial)
    try:
        revisions = learn_instrument(owner, "first", 2.0)
        learn_instrument(owner, "second", -0.5)
        condense(owner, "first")
        condense(owner, "second")
        memory = canonical_json_bytes([chart.as_dict() for chart in owner.state.charts])
        tick = owner.state.logical_tick
        kwargs = {"stimuli": {"first": {"first:input": 0.75}}, "context": CONTEXT, "ticks": 3}
        started = perf_counter()
        advance = owner.advance_transceivers("receive:once", **kwargs)
        publication_seconds = perf_counter() - started
        identity = owner.state.state_sha256
        replay = owner.advance_transceivers("receive:once", **kwargs)
        require(owner.state.state_sha256 == identity, "operation replay consumed stimulus twice")
        require(canonical_json_bytes(replay["receipt"]) == canonical_json_bytes(advance["receipt"]), "replay did not return the original response")
        try:
            owner.advance_transceivers("receive:once", **{**kwargs, "ticks": 2})
        except FieldIntelligenceError as exc:
            require(exc.code == "OPERATION_CONFLICT", "conflicting stimulus returned wrong failure")
        else:
            raise RuntimeError("conflicting operation identity was accepted")
        bundle = owner.state.encode_bundle()
        require(AtlasState.decode_bundle(bundle).state_sha256 == identity, "bundle lost transceiver phase")
        owner.close()
        owner = FieldIntelligenceOwner(home)
        require(owner.state.state_sha256 == identity, "restart lost transceiver phase")
        read_identity = owner.state.state_sha256
        owner.inspect_transceivers()
        require(owner.state.state_sha256 == read_identity, "inspection advanced the field")
        try:
            owner.advance_transceivers("wrong-context", stimuli={"first": {"first:input": 1.0}}, context={"mechanism": "disconnected"})
        except FieldIntelligenceError as exc:
            require(exc.code == "TRANSCEIVER_INAPPLICABLE", "guard did not reject the inappropriate interpretation")
        else:
            raise RuntimeError("guarded unit accepted the wrong mechanism")
        require(owner.state.state_sha256 == read_identity, "failed guard mutated temporal state")
        connection = {"source": "first", "output": "first:output", "target": "second", "input": "second:input"}
        state = owner.state
        connected, receipt = owner.atlas.advance_transceivers(
            state, stimuli={"first": {"first:input": 0.5}, "second": {}}, context=CONTEXT,
            ticks=4, connections=(connection,),
        )
        reordered, _ = owner.atlas.advance_transceivers(
            state, stimuli={"second": {}, "first": {"first:input": 0.5}}, context=CONTEXT,
            ticks=4, connections=(connection,),
        )
        require(connected.state_sha256 == reordered.state_sha256, "assembly execution depends on mapping iteration order")
        source_value = inspect_transceiver(state.transceiver("first").kernel, state.transceiver("first").working_state)["values"]["first:output"]
        manual_working, _ = advance_transceiver(
            state.transceiver("second").kernel, state.transceiver("second").working_state,
            inputs={"second:input": source_value},
            input_errors={"second:input": inspect_transceiver(state.transceiver("first").kernel, state.transceiver("first").working_state)["error_bound"]},
        )
        first_tick, _ = owner.atlas.advance_transceivers(
            state, stimuli={"first": {"first:input": 0.5}, "second": {}}, context=CONTEXT,
            connections=(connection,),
        )
        require(canonical_json_bytes(manual_working) == canonical_json_bytes(first_tick.transceiver("second").working_state), "connection lost its explicit one-tick delay")
        # A read-only diagnostic fork changes ONLY a learned field covariance.
        original = state.chart("first")
        numeric = original.numeric_field
        covariance = original.covariance()
        reflection = torch.eye(len(original.scope), dtype=torch.float64)
        reflection[-1, -1] = -1.0
        original.engine._put_covariance(original.engine._parts(numeric), 0, reflection @ covariance @ reflection)
        changed = owner.atlas.replace_chart(state, replace(original, _numeric_field=numeric, version=original.version + 1))
        require(changed.transceiver("first").status == "stale", "parent change did not invalidate derived transceiver")
        require(changed.transceiver("second") is state.transceiver("second"), "local intervention invalidated an unrelated unit")
        changed, _ = owner.atlas.condense_transceiver(
            changed, transceiver_id="first", chart_ids=("first",), input_ids=("first:input",),
            output_ids=("first:output",), context=CONTEXT, rank=16, error_allowance=1e-3,
            input_bound=4.0, horizon_ticks=128,
        )
        ordinary = trace(state.transceiver("first").kernel, "first", [0.75] * 32)
        intervened = trace(changed.transceiver("first").kernel, "first", [0.75] * 32)
        selective_difference = abs(ordinary["values"][-1] - intervened["values"][-1])
        require(selective_difference > 0.1, "learned field intervention did not change transmitted response")
        require(memory == canonical_json_bytes([chart.as_dict() for chart in owner.state.charts]), "diagnostic fork contaminated the owner")
        require(owner.state.logical_tick == tick, "execution manufactured observed evidence")
        old_manifest = owner.checkpoints.current_manifest_sha256
        preview = owner.preview_forget((revisions[0],))
        owner.forget(
            operation_id="forget:first-source", preview_id=preview["preview_id"], revision_ids=(revisions[0],),
            grant=AuthorityGrant(
                grant_id="forget:scenario", issuer="scenario", generation=owner.authority_generation,
                operation="forget", target=sha256_value(sorted((revisions[0],))), scope="transceiver-scenario",
            ), scope="transceiver-scenario",
        )
        stale = owner.state.transceiver("first")
        require(stale.status == "stale" and stale.kernel is None and stale.working_state is None, "revocation retained executable derived knowledge")
        owner.advance_transceivers("unrelated:after-forget", stimuli={"second": {"second:input": 0.25}}, context=CONTEXT)
        try:
            owner.checkpoints.load_version(old_manifest)
        except FieldIntelligenceError as exc:
            require(exc.code == "STALE_REVOCATION", "revoked rollback returned wrong error")
        else:
            raise RuntimeError("old checkpoint revived a revoked transceiver")
        return {
            "publication_seconds": publication_seconds, "exact_restart_and_bundle": True,
            "exactly_once_stimulus": True, "conflicting_replay_rejected": True,
            "read_only_inspection": True, "guard_rejection_atomic": True,
            "synchronous_composition": True, "connection_delay_ticks": 1,
            "composition_receipt": receipt, "selective_field_intervention_difference": selective_difference,
            "unrelated_transceiver_preserved": True, "revoked_realization_removed": True,
            "revoked_checkpoint_rejected": True, "live_model_calls": 0,
        }
    finally:
        owner.close()


@dataclass(frozen=True)
class InstrumentSpec:
    name: str
    input_names: tuple[str, ...]
    context: dict[str, str]

    def variable(self, role: str) -> str:
        return f"{self.name}:{role}"


class CurriculumSession:
    """Experiment orchestration; the canonical owner is the only learner."""

    def __init__(self, home: Path, *, seed: int, ticks: int = 64) -> None:
        self.home, self.seed, self.default_ticks = home, seed, ticks
        initial = AtlasState(resonant_workspace=initial_workspace(
            ResonantProfile(beta=0.0, damping=0.5),
        ))
        self.owner = FieldIntelligenceOwner(home, initial_state=initial)
        self.sequence = 0
        self.priors: dict[str, Mapping[str, Any]] = {}
        self.training_hashes: set[str] = set()
        self.heldout_hashes: set[str] = set()
        self.training_sources: list[dict[str, str]] = []
        self.builds: list[Mapping[str, Any]] = []
        self.refusals: list[Mapping[str, Any]] = []
        self.costs = {name: 0.0 for name in (
            "configuration_seconds", "admission_seconds", "condensation_publication_seconds",
            "prior_diagnostic_build_seconds", "evaluation_seconds", "owner_execution_seconds",
            "restart_seconds",
        )}

    def operation(self, label: str) -> str:
        self.sequence += 1
        return f"curriculum:{self.sequence}:{label}"

    def memory_identity(self) -> str:
        return sha256_value([chart.as_dict() for chart in self.owner.state.charts])

    def chart_identity(self, spec: InstrumentSpec) -> str:
        return sha256_value(self.owner.state.chart(spec.name).as_dict())

    def configure(
        self, name: str, *, input_names: tuple[str, ...] = ("input",),
        context: Mapping[str, str] | None = None, learning_mode: str = "stationary",
        recency_half_life: float | None = None,
    ) -> InstrumentSpec:
        spec = InstrumentSpec(name, tuple(input_names), dict(context or {
            "mechanism": "connected", "regime": "normal",
        }))
        started = perf_counter()
        self.owner.configure_variable(self.operation("configure"), VariableSpec(
            spec.variable("bias"), kind="constant", constant=1.0,
        ))
        for role in (*spec.input_names, "output"):
            self.owner.configure_variable(self.operation("configure"), VariableSpec(
                spec.variable(role), lower=-40.0, upper=40.0,
            ))
        self.owner.configure_chart(self.operation("configure"), RelationChart.empty(
            chart_id=name, scope=tuple(spec.variable(role) for role in (
                "bias", *spec.input_names, "output",
            )), ridge=0.01, prior_mass=1e-4, observation_norm_bound=100.0,
            learning_mode=learning_mode, recency_half_life=recency_half_life,
            guards=tuple(Guard(key, "eq", value) for key, value in spec.context.items()),
        ))
        self.costs["configuration_seconds"] += perf_counter() - started
        identity = self.owner.state.state_sha256
        try:
            self.owner.condense_transceiver(
                self.operation("untrained-refusal"), transceiver_id=name, chart_ids=(name,),
                input_ids=tuple(spec.variable(role) for role in spec.input_names),
                output_ids=(spec.variable("output"),), context=spec.context,
            )
        except FieldIntelligenceError as exc:
            require(exc.code == "UNSUPPORTED_TRANSCEIVER", "unexpected untrained refusal")
            self.refusals.append({"instrument": name, "code": exc.code})
        else:
            raise RuntimeError("a zero-support chart was admitted as a trained transceiver")
        require(identity == self.owner.state.state_sha256, "untrained refusal changed state")
        # This is a diagnostic evaluation of the actual zero-support prior, not
        # a production realization and not fabricated support for condensation.
        started = perf_counter()
        problem = self.owner.atlas._resonant_problem(
            self.owner.state, (self.owner.state.chart(name),), {}, (),
        )
        assert problem is not None
        problem = replace(problem, observed={
            spec.variable("bias"): 1.0,
            **{spec.variable(role): 0.0 for role in spec.input_names},
        }, affine_constraints=None)
        workspace = self.owner.state.resonant_workspace
        assert workspace is not None
        kernel, _, _ = condense_workspace(
            workspace, problem,
            input_ids=tuple(spec.variable(role) for role in spec.input_names),
            output_ids=(spec.variable("output"),), rank=0,
            input_bound=8.0, horizon_ticks=4096, error_allowance=1e-3,
        )
        self.priors[name] = kernel
        self.costs["prior_diagnostic_build_seconds"] += perf_counter() - started
        return spec

    @staticmethod
    def data_hash(spec: InstrumentSpec, inputs: Mapping[str, float], target: float) -> str:
        return sha256_value({
            "instrument": spec.name, "context": spec.context,
            "inputs": dict(inputs), "target": float(target),
        })

    def admit(
        self, spec: InstrumentSpec, inputs: Mapping[str, float], target: float, *,
        record_id: str, metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        require(set(inputs) == set(spec.input_names), "training observation has wrong roles")
        metadata = dict(metadata or {})
        require(metadata.get("split", "train") == "train", "heldout outcome entered learning")
        digest = self.data_hash(spec, inputs, target)
        require(digest not in self.heldout_hashes, "heldout record entered training")
        source = SourceInput(
            source_id=f"curriculum:{self.seed}:{spec.name}:{record_id}",
            content=canonical_json_bytes({
                "instrument": spec.name, "record_id": record_id, "inputs": dict(inputs),
                "output": float(target), "context": spec.context,
                "metadata": {**metadata, "split": "train"},
            }),
            media_type="application/json", codec="utf-8", observed_timestamp=record_id,
            scope="field-curriculum", claim_category="controlled-world-observation",
            fidelity="exact-record", labels=("field-curriculum", "train"),
        )
        started = perf_counter()
        result = self.owner.admit_observation(
            operation_id=self.operation("admit"), source=source,
            values={spec.variable("bias"): 1.0, spec.variable("output"): float(target),
                    **{spec.variable(role): float(value) for role, value in inputs.items()}},
            context=spec.context, target_chart_ids=(spec.name,),
        )
        self.costs["admission_seconds"] += perf_counter() - started
        self.training_hashes.add(digest)
        self.training_sources.append({
            "source_id": source.source_id, "revision_id": source.revision_id,
            "data_sha256": digest,
        })
        return result

    def kernel(self, spec: InstrumentSpec) -> Mapping[str, Any]:
        existing = next((row for row in self.owner.state.transceivers
                         if row.transceiver_id == spec.name), None)
        if existing is None or existing.status != "active":
            started = perf_counter()
            result = self.owner.condense_transceiver(
                self.operation("condense"), transceiver_id=spec.name,
                chart_ids=(spec.name,),
                input_ids=tuple(spec.variable(role) for role in spec.input_names),
                output_ids=(spec.variable("output"),), context=spec.context,
                rank=16, input_bound=8.0, horizon_ticks=4096, error_allowance=1e-3,
            )
            elapsed = perf_counter() - started
            self.costs["condensation_publication_seconds"] += elapsed
            self.builds.append({
                "instrument": spec.name, "receipt": result["receipt"],
                "publication_seconds": elapsed,
                "kernel_bytes": len(canonical_json_bytes(
                    self.owner.state.transceiver(spec.name).kernel,
                )),
            })
        kernel = self.owner.state.transceiver(spec.name).kernel
        assert kernel is not None
        return kernel

    def evaluate(
        self, spec: InstrumentSpec, probes: list[dict[str, Any]], *, label: str,
        carry: bool = False, ticks: int | None = None, feedback_input: str | None = None,
    ) -> Mapping[str, Any]:
        require(bool(probes), "empty heldout evaluation")
        require(feedback_input is None or feedback_input in spec.input_names,
                "feedback must address an input role")
        for probe in probes:
            require(set(probe["inputs"]) == set(spec.input_names), "heldout roles mismatch")
            digest = self.data_hash(spec, probe["inputs"], probe["target"])
            require(digest not in self.training_hashes, "training record entered heldout set")
            self.heldout_hashes.add(digest)
        before, clock = self.memory_identity(), self.owner.state.logical_tick
        supported = bool(self.owner.state.chart(spec.name).contributions)
        kernel = self.kernel(spec) if supported else self.priors[spec.name]
        ticks = self.default_ticks if ticks is None else ticks
        conditions: dict[str, Any] = {}
        for name in ("trained_full", "trained_transceiver", "untrained_prior"):
            current = self.priors[spec.name] if name == "untrained_prior" else kernel
            working = reset_transceiver(current)
            predictions: list[float | None] = []
            bounds: list[float | None] = []
            resolved: list[bool] = []
            failures: list[dict[str, Any]] = []
            effective_inputs: list[dict[str, float]] = []
            counts = {key: 0 for key in ("full_steps", "reduced_steps",
                                        "operator_applications", "nonlinear_iterations")}
            started = perf_counter()
            for index, probe in enumerate(probes):
                if not carry or index == 0:
                    working = reset_transceiver(current)
                inputs = dict(probe["inputs"])
                input_errors: dict[str, float] = {}
                if feedback_input is not None and index:
                    if predictions[-1] is None:
                        predictions.append(None)
                        bounds.append(None)
                        resolved.append(False)
                        continue
                    inputs[feedback_input] = predictions[-1]
                    input_errors[spec.variable(feedback_input)] = bounds[-1] or 0.0
                effective_inputs.append(inputs)
                try:
                    working, receipt = advance_transceiver(
                        current, working,
                        inputs={spec.variable(role): float(value) for role, value in inputs.items()},
                        input_errors=input_errors, ticks=ticks,
                        force_full=name != "trained_transceiver",
                    )
                except ResonantNumericalError as exc:
                    failures.append({"index": index, "message": str(exc)})
                    predictions.append(None)
                    bounds.append(None)
                    resolved.append(False)
                    continue
                predictions.append(float(receipt["values"][spec.variable("output")]))
                bounds.append(float(receipt["error_bound"]))
                resolved.append(bool(receipt["resolved"]))
                for key in counts:
                    counts[key] += int(receipt["counts"][key])
            elapsed = perf_counter() - started
            errors = np.array([
                abs(value - float(probe["target"]))
                for probe, value in zip(probes, predictions) if value is not None
            ])
            answered_rmse = float(np.sqrt(np.mean(errors**2))) if errors.size else None
            conditions[name] = {
                "supported": supported and name != "untrained_prior",
                "diagnostic_only": not supported or name == "untrained_prior",
                "rmse": answered_rmse if errors.size == len(probes) else None,
                "answered_rmse": answered_rmse,
                "mae": float(errors.mean()) if errors.size else None,
                "max_abs_error": float(errors.max()) if errors.size else None,
                "coverage": int(errors.size) / len(probes),
                "resolved_fraction": sum(resolved) / len(probes),
                "success_fraction": int(np.count_nonzero(errors <= 0.05)) / len(probes),
                "admissible_success_fraction": sum(
                    value is not None and ok and abs(value - float(probe["target"])) <= 0.05
                    for value, ok, probe in zip(predictions, resolved, probes)
                ) / len(probes) if supported and name != "untrained_prior" else 0.0,
                "predictions": predictions, "numerical_bounds": bounds,
                "effective_inputs": effective_inputs, "failures": failures,
                "work": counts, "elapsed_seconds": elapsed,
            }
            self.costs["evaluation_seconds"] += elapsed
        full, compact = conditions["trained_full"], conditions["trained_transceiver"]
        comparisons = [
            (abs(a-b), float(ea or 0.0)+float(eb or 0.0)+1e-8)
            for a, b, ea, eb in zip(
                full["predictions"], compact["predictions"],
                full["numerical_bounds"], compact["numerical_bounds"],
            ) if a is not None and b is not None
        ]
        enclosed = all(error <= allowance for error, allowance in comparisons)
        require(enclosed, "compact response escaped its numerical enclosure")
        require(before == self.memory_identity(), "evaluation changed learned support")
        require(clock == self.owner.state.logical_tick, "evaluation added evidence")
        return {
            "label": label, "instrument": spec.name, "probes": probes,
            "ticks_per_prediction": ticks, "carry": carry, "feedback_input": feedback_input,
            "conditions": conditions,
            "approximation": {
                "maximum_difference": max((row[0] for row in comparisons), default=None),
                "within_bounds": enclosed if comparisons else None,
                "paired_count": len(comparisons),
            },
            "learned_memory_unchanged": True, "evidence_clock_unchanged": True,
        }

    def restart_probe(self, spec: InstrumentSpec, inputs: Mapping[str, float]) -> Mapping[str, Any]:
        kernel = self.kernel(spec)
        self.owner.reset_transceiver(self.operation("restart-reset"), transceiver_id=spec.name)
        stimuli = {spec.name: {spec.variable(role): float(value) for role, value in inputs.items()}}
        self.owner.advance_transceivers(
            self.operation("restart-prefix"), stimuli=stimuli, context=spec.context, ticks=7,
        )
        saved = self.owner.state.transceiver(spec.name).working_state
        assert saved is not None
        expected, _ = advance_transceiver(kernel, saved, inputs=stimuli[spec.name], ticks=7)
        identity, memory, clock = (
            self.owner.state.state_sha256, self.memory_identity(), self.owner.state.logical_tick,
        )
        bundle = self.owner.state.encode_bundle()
        require(AtlasState.decode_bundle(bundle).state_sha256 == identity, "bundle lost curriculum")
        started = perf_counter()
        self.owner.close()
        self.owner = FieldIntelligenceOwner(self.home)
        restart_seconds = perf_counter() - started
        self.costs["restart_seconds"] += restart_seconds
        require(self.owner.state.state_sha256 == identity, "restart changed canonical field")
        operation = self.operation("restart-suffix")
        result = self.owner.advance_transceivers(
            operation, stimuli=stimuli, context=spec.context, ticks=7,
        )
        require(canonical_json_bytes(self.owner.state.transceiver(spec.name).working_state)
                == canonical_json_bytes(expected), "restart changed temporal continuation")
        after = self.owner.state.state_sha256
        self.owner.advance_transceivers(operation, stimuli=stimuli, context=spec.context, ticks=7)
        require(after == self.owner.state.state_sha256, "retry duplicated heldout stimulus")
        require(memory == self.memory_identity(), "restart execution changed knowledge")
        require(clock == self.owner.state.logical_tick, "restart execution admitted evidence")
        return {
            "exact_state_restart": True, "exact_bundle": True,
            "exact_temporal_continuation": True, "exactly_once_retry": True,
            "learned_memory_unchanged": True, "evidence_clock_unchanged": True,
            "restart_seconds": restart_seconds, "state_sha256": after,
            "response": result["receipt"]["transceivers"][spec.name]["values"],
        }

    def usage(self) -> Mapping[str, Any]:
        usage = dict(self.owner.inspect()["capacity"]["usage"])
        maximum = max((float(torch.max(torch.abs(chart.numeric_field)))
                       for chart in self.owner.state.charts), default=0.0)
        require(bool(np.isfinite(maximum)), "learned field is nonfinite")
        return {
            **usage, "learned_field_max_abs": maximum,
            "evidence_count": self.owner.evidence.event_count,
            "data_home_bytes": sum(path.stat().st_size for path in self.home.rglob("*")
                                   if path.is_file()),
        }


def affine_curriculum(
    session: CurriculumSession, rng: np.random.Generator, *, samples: int,
) -> tuple[Mapping[str, Any], tuple[InstrumentSpec, ...], dict[str, list[dict[str, Any]]]]:
    # These laws belong to the controlled environment, never to the predictor.
    laws = {"amplifier": (1.3, 0.25), "inverter": (-0.7, -0.4), "offset": (0.45, 1.0)}
    specs = tuple(session.configure(name) for name in laws)
    heldout_x = (-1.75, -0.9, -0.2, 0.6, 1.25, 1.9, -3.1, -2.6, 2.5, 3.2)
    probes = {
        spec.name: [{
            "id": f"affine:heldout:{spec.name}:{index}",
            "inputs": {"input": value},
            "target": laws[spec.name][0]*value + laws[spec.name][1],
            "partition": "interpolation" if abs(value) < 2 else "extrapolation",
        } for index, value in enumerate(heldout_x)]
        for spec in specs
    }
    training = {spec.name: rng.uniform(-2.0, 2.0, size=samples).tolist() for spec in specs}
    milestones = sorted({0, min(4, samples), min(12, samples), samples})
    curve: list[dict[str, Any]] = []
    previous = 0
    for size in milestones:
        for index in range(previous, size):
            for position in rng.permutation(len(specs)):
                spec = specs[int(position)]
                value = training[spec.name][index]
                gain, offset = laws[spec.name]
                session.admit(
                    spec, {"input": value}, gain*value + offset,
                    record_id=f"affine:train:{index}",
                    metadata={"split": "train", "round": index, "stage": "affine"},
                )
        evaluations = {spec.name: session.evaluate(
            spec, probes[spec.name], label=f"affine:{size}:{spec.name}",
        ) for spec in specs}
        curve.append({
            "observations_per_instrument": size, "evaluations": evaluations,
            "usage": session.usage(),
        })
        print(json.dumps({
            "stage": "affine", "seed": session.seed, "observations_per_instrument": size,
            "rmse": {name: row["conditions"]["trained_transceiver"]["rmse"]
                     for name, row in evaluations.items()},
        }), flush=True)
        previous = size
    return {
        "laws": {name: {"gain": gain, "offset": offset} for name, (gain, offset) in laws.items()},
        "training_inputs": training, "heldout_probes": probes, "learning_curve": curve,
        "supplied_structure": "scalar variables, chart identities, context, and ports",
        "training_interval": [-2.0, 2.0],
        "task_error_is_distinct_from_numerical_approximation": True,
    }, specs, probes


def composition_curriculum(
    session: CurriculumSession, specs: tuple[InstrumentSpec, ...],
    laws: Mapping[str, Mapping[str, float]],
) -> Mapping[str, Any]:
    memory, clock = session.memory_identity(), session.owner.state.logical_tick
    cases: list[dict[str, Any]] = []
    for first, second in ((specs[0], specs[1]), (specs[1], specs[2]), (specs[0], specs[2])):
        for value in (2.2, -2.4):
            target = laws[second.name]["gain"] * (
                laws[first.name]["gain"]*value + laws[first.name]["offset"]
            ) + laws[second.name]["offset"]
            condition_rows: dict[str, Any] = {}
            for condition in ("trained_full", "trained_transceiver", "untrained_prior"):
                started = perf_counter()
                if condition == "untrained_prior":
                    kernels = [session.priors[spec.name] for spec in (first, second)]
                    working = [reset_transceiver(kernel) for kernel in kernels]
                    counts = {"full_steps": 0, "reduced_steps": 0,
                              "operator_applications": 0, "nonlinear_iterations": 0}
                    response: Mapping[str, Any] = {}
                    for _ in range(session.default_ticks):
                        previous = inspect_transceiver(kernels[0], working[0])
                        working[0], sender = advance_transceiver(
                            kernels[0], working[0], inputs={first.variable("input"): value},
                            force_full=True,
                        )
                        working[1], response = advance_transceiver(
                            kernels[1], working[1],
                            inputs={second.variable("input"): previous["values"][first.variable("output")]},
                            input_errors={second.variable("input"): previous["error_bound"]},
                            force_full=True,
                        )
                        for receipt in (sender, response):
                            for key in counts:
                                counts[key] += receipt["counts"][key]
                else:
                    for spec in (first, second):
                        session.kernel(spec)
                        session.owner.reset_transceiver(
                            session.operation("composition-reset"), transceiver_id=spec.name,
                        )
                    counts = {key: 0 for key in (
                        "full_steps", "reduced_steps", "operator_applications", "nonlinear_iterations",
                    )}
                    # Each publication has a 64 KiB typed-receipt ceiling.
                    # Carry the same state and wiring across bounded batches.
                    for start in range(0, session.default_ticks, 8):
                        result = session.owner.advance_transceivers(
                            session.operation("composition"),
                            stimuli={first.name: {first.variable("input"): value}, second.name: {}},
                            connections=({
                                "source": first.name, "output": first.variable("output"),
                                "target": second.name, "input": second.variable("input"),
                            },), context=first.context, ticks=min(8, session.default_ticks-start),
                            force_full=condition == "trained_full",
                        )
                        response = result["receipt"]["transceivers"][second.name]
                        for step in result["receipt"]["steps"]:
                            for key in counts:
                                counts[key] += step["counts"][key]
                elapsed = perf_counter() - started
                if condition != "untrained_prior":
                    session.costs["owner_execution_seconds"] += elapsed
                prediction = float(response["values"][second.variable("output")])
                condition_rows[condition] = {
                    "prediction": prediction, "absolute_error": abs(prediction-target),
                    "numerical_bound": float(response["error_bound"]),
                    "resolved": bool(response["resolved"]), "work": counts,
                    "elapsed_seconds": elapsed, "production_path": condition != "untrained_prior",
                    "cost_scope": "reset and owner publication" if condition != "untrained_prior"
                                  else "diagnostic numerical prior only",
                }
            full, compact = condition_rows["trained_full"], condition_rows["trained_transceiver"]
            difference = abs(full["prediction"] - compact["prediction"])
            require(difference <= full["numerical_bound"] + compact["numerical_bound"] + 1e-8,
                    "connected compact response escaped enclosure")
            cases.append({
                "first": first.name, "second": second.name, "input": value, "target": target,
                "conditions": condition_rows, "compact_full_difference": difference,
            })
    require(memory == session.memory_identity(), "composition changed learned memory")
    require(clock == session.owner.state.logical_tick, "composition admitted predictions")
    return {
        "cases": cases, "connection_delay_ticks": 1,
        "new_pair_training_observations": 0,
        "shared_external_target": "composition of the same independently specified affine laws",
        "connections_are_supplied": True,
        "learned_memory_unchanged": True, "evidence_clock_unchanged": True,
        "rmse": {name: float(np.sqrt(np.mean([
            case["conditions"][name]["absolute_error"]**2 for case in cases
        ]))) for name in ("trained_full", "trained_transceiver", "untrained_prior")},
    }


def _temporal_jsonable(value: Any) -> Any:
    """Convert numpy scalars and nested mappings to JSON-native values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _temporal_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_temporal_jsonable(item) for item in value]
    return value


def _temporal_rollout(
    stimuli: Any,
    *,
    offset: float,
    law: Mapping[str, Any],
) -> list[float]:
    """Replay a stimulus sequence through the one fixed affine recurrence."""
    coefficients = law["coefficients"]
    outcomes: list[float] = []
    previous_output = float(law["initial_output"])
    for index, current in enumerate(stimuli):
        lag1 = float(stimuli[index - 1]) if index >= 1 else 0.0
        lag2 = float(stimuli[index - 2]) if index >= 2 else 0.0
        output = (
            float(coefficients["input"]) * float(current)
            + float(coefficients["input_lag1"]) * lag1
            + float(coefficients["input_lag2"]) * lag2
            + float(coefficients["output_lag1"]) * previous_output
            + float(coefficients["offset"]) * float(offset)
        )
        outcomes.append(float(output))
        previous_output = float(output)
    return outcomes


def _temporal_world_episode(
    *,
    seed: int,
    split: str,
    episode_index: int,
    steps: int,
    law: Mapping[str, Any],
) -> dict[str, Any]:
    """Generate one world trajectory from a seed independent of all other episodes."""
    episode_rng = np.random.default_rng(int(seed))
    stimuli = episode_rng.uniform(-1.0, 1.0, size=int(steps)).astype(np.float64)
    offset = float(episode_rng.uniform(-0.35, 0.35))
    outcomes = _temporal_rollout(stimuli, offset=offset, law=law)
    world_id = f"temporal-world-{split}-{episode_index:03d}"
    return {
        "episode_id": f"temporal-{split}-episode-{episode_index:03d}",
        "world_id": world_id,
        "split": split,
        "episode_index": int(episode_index),
        "seed": int(seed),
        "steps": int(steps),
        "offset": offset,
        "stimuli": [float(value) for value in stimuli],
        "outcomes": outcomes,
        "stimulus_sha256": sha256_value([float(value) for value in stimuli]),
        "outcome_sha256": sha256_value(outcomes),
        "world_law_id": law["law_id"],
    }




def _temporal_rows(episode: Mapping[str, Any], *, warmup: int = 2) -> list[dict[str, Any]]:
    """Expose post-warmup rows with supplied, observed history features."""
    stimuli = episode["stimuli"]
    outcomes = episode["outcomes"]
    rows: list[dict[str, Any]] = []
    for index in range(int(warmup), len(stimuli)):
        features = {
            "input": float(stimuli[index]),
            "input_lag1": float(stimuli[index - 1]),
            "input_lag2": float(stimuli[index - 2]),
            "output_lag1": float(outcomes[index - 1]),
            "offset": float(episode["offset"]),
        }
        target = float(outcomes[index])
        current_features = {"input": features["input"]}
        rows.append(
            {
                "episode_id": str(episode["episode_id"]),
                "world_id": str(episode["world_id"]),
                "split": str(episode["split"]),
                "episode_index": int(episode["episode_index"]),
                "step": int(index),
                "features": features,
                "current_features": current_features,
                "target": target,
                "feature_sha256": {
                    "current_only": sha256_value(current_features),
                    "observed_history": sha256_value(features),
                },
                "target_sha256": sha256_value({"target": target}),
            }
        )
    return rows


def _temporal_probe(row: Mapping[str, Any], *, representation: str) -> dict[str, Any]:
    inputs = row["current_features"] if representation == "current_only" else row["features"]
    return {
        "id": f"{row['split']}:{row['episode_id']}:step-{int(row['step']):03d}:{representation}",
        "inputs": {str(key): float(value) for key, value in inputs.items()},
        "target": float(row["target"]),
    }
def _temporal_condition_summary(
    reports: list[Mapping[str, Any]],
    *,
    condition: str,
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate raw per-episode reports without hiding missing predictions."""
    predictions: list[float | None] = []
    bounds: list[float | None] = []
    work: dict[str, int] = {}
    elapsed = 0.0
    supported_values: list[bool] = []
    memory_values: list[bool] = []
    clock_values: list[bool] = []
    for report in reports:
        condition_row = report.get("conditions", {}).get(condition, {})
        predictions.extend(condition_row.get("predictions", []))
        bounds.extend(condition_row.get("numerical_bounds", []))
        elapsed += float(condition_row.get("elapsed_seconds", 0.0) or 0.0)
        supported_values.append(bool(condition_row.get("supported", False)))
        if "learned_memory_unchanged" in report:
            memory_values.append(bool(report["learned_memory_unchanged"]))
        if "evidence_clock_unchanged" in report:
            clock_values.append(bool(report["evidence_clock_unchanged"]))
        for key, value in condition_row.get("work", {}).items():
            if isinstance(value, (int, float, np.integer, np.floating)):
                work[str(key)] = work.get(str(key), 0) + int(value)
    targets = [float(row["target"]) for row in rows]
    # Session reports preserve one prediction slot per probe.  Keep that shape,
    # and treat a length mismatch as a measurement rather than inventing values.
    paired = min(len(targets), len(predictions))
    paired_targets = targets[:paired]
    paired_predictions = predictions[:paired]
    answered = [
        (target, float(prediction))
        for target, prediction in zip(paired_targets, paired_predictions)
        if prediction is not None
    ]
    errors = [prediction - target for target, prediction in answered]
    abs_errors = [abs(error) for error in errors]
    missing = len(targets) != len(predictions) or any(prediction is None for prediction in paired_predictions)
    answered_rmse = float(np.sqrt(np.mean(np.square(errors)))) if errors else None
    return {
        "supported": bool(supported_values) and all(supported_values),
        "rmse": None if missing or not errors else answered_rmse,
        "answered_rmse": answered_rmse,
        "mae": float(np.mean(abs_errors)) if abs_errors else None,
        "max_abs_error": max(abs_errors) if abs_errors else None,
        "coverage": float(len(answered) / len(targets)) if targets else 0.0,
        "success_fraction": float(sum(error <= 0.05 for error in abs_errors) / len(targets)) if targets else 0.0,
        "predictions": [_temporal_jsonable(prediction) for prediction in predictions],
        "numerical_bounds": [_temporal_jsonable(bound) for bound in bounds],
        "work": work,
        "elapsed_seconds": elapsed,
        "learned_memory_unchanged": all(memory_values) if memory_values else None,
        "evidence_clock_unchanged": all(clock_values) if clock_values else None,
        "prediction_count": len(predictions),
        "target_count": len(targets),
    }


def _temporal_eval_episodes(
    session: Any,
    spec: Any,
    episodes: list[dict[str, Any]],
    *,
    representation: str,
    label: str,
    carry: bool,
    ticks: int,
    feedback_input: str | None = None,
    reverse: bool = False,
) -> dict[str, Any]:
    """Evaluate episode-by-episode so carried state never crosses an episode boundary."""
    reports: list[Mapping[str, Any]] = []
    rows_for_summary: list[Mapping[str, Any]] = []
    episode_lengths: list[int] = []
    for episode_index, episode in enumerate(episodes):
        rows = _temporal_rows(episode)
        if reverse:
            rows = list(reversed(rows))
        episode_lengths.append(len(rows))
        probes = [_temporal_probe(row, representation=representation) for row in rows]
        report = session.evaluate(
            spec,
            probes,
            label=f"{label}:episode-{episode_index:03d}",
            carry=carry,
            ticks=int(ticks),
            feedback_input=feedback_input,
        )
        report_conditions = report.get("conditions", {})
        for condition in ("trained_full", "trained_transceiver", "untrained_prior"):
            condition_row = report_conditions.get(condition, {})
            require(
                len(condition_row.get("predictions", [])) == len(probes),
                f"{label}: {condition} prediction/probe shape changed",
            )
            require(
                len(condition_row.get("numerical_bounds", [])) == len(probes),
                f"{label}: {condition} bound/probe shape changed",
            )
        reports.append(_temporal_jsonable(report))
        rows_for_summary.extend(rows)
    conditions = {
        condition: _temporal_condition_summary(reports, condition=condition, rows=rows_for_summary)
        for condition in ("trained_full", "trained_transceiver", "untrained_prior")
    }
    return {
        "label": label,
        "representation": representation,
        "carry": bool(carry),
        "feedback_input": feedback_input,
        "ticks_per_environment_step": int(ticks),
        "episode_prediction_lengths": episode_lengths,
        "reports_by_episode": reports,
        "conditions": conditions,
    }


def _temporal_reverse_segments(values: list[Any], lengths: list[int]) -> list[Any]:
    aligned: list[Any] = []
    cursor = 0
    for length in lengths:
        aligned.extend(reversed(values[cursor:cursor + int(length)]))
        cursor += int(length)
    aligned.extend(values[cursor:])
    return aligned


def _temporal_presentation_measurement(
    forward: Mapping[str, Any],
    reverse: Mapping[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lengths = [int(value) for value in forward.get("episode_prediction_lengths", [])]
    for condition in ("trained_full", "trained_transceiver", "untrained_prior"):
        fwd = list(forward["conditions"][condition].get("predictions", []))
        rev = _temporal_reverse_segments(
            list(reverse["conditions"][condition].get("predictions", [])),
            lengths,
        )
        paired = min(len(fwd), len(rev))
        differences = [
            abs(float(fwd[index]) - float(rev[index]))
            for index in range(paired)
            if fwd[index] is not None and rev[index] is not None
        ]
        result[condition] = {
            "maximum_aligned_presentation_prediction_difference": max(differences) if differences else None,
            "mean_aligned_presentation_prediction_difference": float(np.mean(differences)) if differences else None,
            "paired_prediction_count": int(len(differences)),
            "forward_predictions": fwd,
            "reverse_predictions_aligned_to_forward": rev,
        }
    return result


def _temporal_pulse_comparison(
    session: CurriculumSession, law: Mapping[str, Any],
    current_spec: InstrumentSpec, history_spec: InstrumentSpec,
    heldout_episodes: list[dict[str, Any]],
) -> Mapping[str, Any]:
    """Swap two pulses, then compare responses under an identical zero-input tail."""
    pairs: list[dict[str, Any]] = []
    for original in heldout_episodes:
        pulse_values = original["stimuli"][2:4]
        worlds: dict[str, dict[str, Any]] = {}
        for ordering, pulses in (("forward", pulse_values), ("reversed", pulse_values[::-1])):
            stimuli = [0.0, 0.0, *pulses, *([0.0]*6)]
            outcomes = _temporal_rollout(stimuli, offset=original["offset"], law=law)
            worlds[ordering] = {
                **original,
                "episode_id": f"{original['episode_id']}:pulse-{ordering}",
                "world_id": f"{original['world_id']}:pulse-{ordering}",
                "steps": len(stimuli), "stimuli": stimuli, "outcomes": outcomes,
                "stimulus_sha256": sha256_value(stimuli),
                "outcome_sha256": sha256_value(outcomes),
            }
        true_tail_delta = [
            a-b for a, b in zip(worlds["forward"]["outcomes"][4:],
                               worlds["reversed"]["outcomes"][4:])
        ]
        representations: dict[str, Any] = {}
        for name, spec, representation, ticks, carry, feedback in (
            ("current_only_raw", current_spec, "current_only", 1, True, None),
            ("current_only_conditional", current_spec, "current_only",
             session.default_ticks, True, None),
            ("history_closed_loop", history_spec, "observed_history",
             session.default_ticks, False, "output_lag1"),
        ):
            evaluations = {
                ordering: _temporal_eval_episodes(
                    session, spec, [world], representation=representation,
                    label=f"pulse:{original['episode_id']}:{ordering}:{name}",
                    carry=carry, ticks=ticks, feedback_input=feedback,
                ) for ordering, world in worlds.items()
            }
            deltas: dict[str, Any] = {}
            for condition in ("trained_full", "trained_transceiver", "untrained_prior"):
                forward = evaluations["forward"]["conditions"][condition]["predictions"][2:]
                reverse = evaluations["reversed"]["conditions"][condition]["predictions"][2:]
                delta = [None if a is None or b is None else a-b for a, b in zip(forward, reverse)]
                complete = len(delta) == len(true_tail_delta) and all(value is not None for value in delta)
                deltas[condition] = {
                    "predicted_tail_difference": delta,
                    "tail_difference_rmse": float(np.sqrt(np.mean([
                        (value-target)**2 for value, target in zip(delta, true_tail_delta)
                    ]))) if complete else None,
                }
            representations[name] = {"evaluations": evaluations, "order_response": deltas}
        pairs.append({
            "worlds": worlds, "true_tail_difference": true_tail_delta,
            "representations": representations,
        })
    return {
        "pairs": pairs, "same_external_law_for_every_condition": True,
        "same_pulses_different_order": True, "identical_zero_input_tail": True,
        "targets_recomputed_from_external_recurrence": True,
        "not_a_presentation_order_test": True,
    }


def temporal_curriculum(session: CurriculumSession, rng: np.random.Generator) -> Mapping[str, Any]:
    """Run one sustained, externally grounded delayed autoregressive stage."""
    stage = "temporal_curriculum"
    context = {"mechanism": "connected", "regime": "normal"}
    law: dict[str, Any] = {
        "law_id": "bounded-delayed-ar-affine-v1",
        "equation": "y_t=a0*x_t+a1*x_(t-1)+a2*x_(t-2)+b*y_(t-1)+c*offset",
        "coefficients": {
            "input": 0.62,
            "input_lag1": 0.18,
            "input_lag2": -0.11,
            "output_lag1": 0.56,
            "offset": 0.14,
        },
        "initial_output": 0.0,
        "stimulus_bound": [-1.0, 1.0],
        "offset_bound": [-0.35, 0.35],
        "output_bound": [-2.18, 2.18],
        "boundedness_argument": "|a0|+|a1|+|a2|+|c|*0.35 <= 0.959 and |b|=0.56<1, so the recurrence bound is 0.959/(1-0.56) < 2.18",
        "offset_mode": "one supplied constant offset per episode",
        "world_authority": "external deterministic generator; never a field prediction",
    }
    current_spec = session.configure(
        f"{stage}:current_only",
        input_names=("input",),
        context=context,
        learning_mode="stationary",
    )
    history_spec = session.configure(
        f"{stage}:observed_history",
        input_names=("input", "input_lag1", "input_lag2", "output_lag1", "offset"),
        context=context,
        learning_mode="stationary",
    )

    # Eight independent ten-step training episodes yield exactly 64 post-warmup
    # observations for each representation.  Holdout seeds and stimuli are disjoint.
    training_episode_count = 8
    training_steps = 10
    heldout_episode_count = 2
    heldout_steps = 14
    all_seeds = [int(value) for value in rng.integers(0, 2**63 - 1, size=training_episode_count + heldout_episode_count)]
    training_seeds = all_seeds[:training_episode_count]
    heldout_seeds = all_seeds[training_episode_count:]
    require(len(set(training_seeds)) == len(training_seeds), "temporal training episode seeds collided")
    require(len(set(heldout_seeds)) == len(heldout_seeds), "temporal heldout episode seeds collided")
    require(not set(training_seeds).intersection(heldout_seeds), "temporal train and heldout seeds overlap")
    training_episodes = [
        _temporal_world_episode(seed=seed, split="train", episode_index=index, steps=training_steps, law=law)
        for index, seed in enumerate(training_seeds)
    ]
    heldout_episodes = [
        _temporal_world_episode(seed=seed, split="heldout", episode_index=index, steps=heldout_steps, law=law)
        for index, seed in enumerate(heldout_seeds)
    ]
    training_rows = [row for episode in training_episodes for row in _temporal_rows(episode)]
    heldout_rows = [row for episode in heldout_episodes for row in _temporal_rows(episode)]
    require(len(training_rows) == 64, "temporal training sample count changed")
    require(len(heldout_rows) == 24, "temporal heldout sample count changed")
    training_world_hash = sha256_value(training_episodes)
    heldout_world_hash = sha256_value(heldout_episodes)
    require(training_world_hash != heldout_world_hash, "temporal split world hashes unexpectedly match")

    admissions: list[dict[str, Any]] = []
    milestones: list[dict[str, Any]] = []
    next_row = 0
    checkpoint_sizes = (16, len(training_rows))
    for checkpoint_size in checkpoint_sizes:
        while next_row < checkpoint_size:
            row = training_rows[next_row]
            base_metadata = {
                "split": "train",
                "stage": stage,
                "world_id": row["world_id"],
                "episode_id": row["episode_id"],
                "step": int(row["step"]),
                "law_id": law["law_id"],
                "source_kind": "external-controlled-measurement",
            }
            for representation, spec, inputs in (
                ("current_only", current_spec, row["current_features"]),
                ("observed_history", history_spec, row["features"]),
            ):
                record_id = f"{stage}:train:{representation}:row-{next_row:03d}"
                metadata = {**base_metadata, "representation": representation}
                result = session.admit(
                    spec,
                    {str(key): float(value) for key, value in inputs.items()},
                    float(row["target"]),
                    record_id=record_id,
                    metadata=metadata,
                )
                source_payload = {"record_id": record_id, "inputs": inputs, "target": row["target"], "metadata": metadata}
                admissions.append(
                    {
                        "record_id": record_id,
                        "representation": representation,
                        "episode_id": row["episode_id"],
                        "world_id": row["world_id"],
                        "step": int(row["step"]),
                        "inputs": _temporal_jsonable(inputs),
                        "target": float(row["target"]),
                        "feature_target_source_sha256": sha256_value(source_payload),
                        "owner_result": _temporal_jsonable(result),
                    }
                )
            next_row += 1
        usage = _temporal_jsonable(session.usage())
        current_64 = _temporal_eval_episodes(
            session,
            current_spec,
            heldout_episodes,
            representation="current_only",
            label=f"{stage}:checkpoint-{checkpoint_size}:current-only:64tick-carried",
            carry=True,
            ticks=int(session.default_ticks),
        )
        history_true = _temporal_eval_episodes(
            session,
            history_spec,
            heldout_episodes,
            representation="observed_history",
            label=f"{stage}:checkpoint-{checkpoint_size}:observed-history:true-past:64tick",
            carry=False,
            ticks=int(session.default_ticks),
        )
        history_closed = _temporal_eval_episodes(
            session,
            history_spec,
            heldout_episodes,
            representation="observed_history",
            label=f"{stage}:checkpoint-{checkpoint_size}:observed-history:closed-loop:64tick",
            carry=False,
            ticks=int(session.default_ticks),
            feedback_input="output_lag1",
        )
        raw_current = _temporal_eval_episodes(
            session,
            current_spec,
            heldout_episodes,
            representation="current_only",
            label=f"{stage}:checkpoint-{checkpoint_size}:raw-current-only:one-field-tick",
            carry=True,
            ticks=1,
        )
        milestones.append(
            {
                "training_observations_per_representation": int(checkpoint_size),
                "training_admissions_total": int(checkpoint_size * 2),
                "usage_after_admission": usage,
                "current_only_carried_transceiver_64tick": current_64,
                "observed_history_conditional_true_past_64tick": history_true,
                "observed_history_closed_loop_predicted_past_64tick": history_closed,
                "raw_current_only_fixed_wave_one_field_tick": raw_current,
            }
        )

    # This is strictly a presentation-order sensitivity control: the same
    # held-out world rows and true outcomes are shown in forward/reversed order.
    # A same-law reversed-stimulus world response, with freshly recomputed
    # outcomes, is a separate experiment owned by the integrating driver.
    final_checkpoint = milestones[-1]
    order_results: dict[str, Any] = {}
    for representation, spec in (("current_only", current_spec), ("observed_history", history_spec)):
        forward = _temporal_eval_episodes(
            session,
            spec,
            heldout_episodes,
            representation=representation,
            label=f"{stage}:presentation-order:forward:{representation}:64tick",
            carry=(representation == "current_only"),
            ticks=int(session.default_ticks),
        )
        reverse = _temporal_eval_episodes(
            session,
            spec,
            heldout_episodes,
            representation=representation,
            label=f"{stage}:presentation-order:reverse:{representation}:64tick",
            carry=(representation == "current_only"),
            ticks=int(session.default_ticks),
            reverse=True,
        )
        order_results[representation] = {
            "measurement_kind": "presentation_order_sensitivity",
            "same_external_world_rows": True,
            "world_ids": [episode["world_id"] for episode in heldout_episodes],
            "world_outcome_hashes": [episode["outcome_sha256"] for episode in heldout_episodes],
            "forward_target_rows": [float(row["target"]) for row in heldout_rows],
            "reverse_target_rows_in_presented_order": [
                float(row["target"])
                for episode in heldout_episodes
                for row in reversed(_temporal_rows(episode))
            ],
            "forward": forward,
            "reverse": reverse,
            "aligned_presentation_measurement": _temporal_presentation_measurement(forward, reverse),
        }

    early_raw = milestones[0]["raw_current_only_fixed_wave_one_field_tick"]["conditions"]["trained_transceiver"]
    final_raw = final_checkpoint["raw_current_only_fixed_wave_one_field_tick"]["conditions"]["trained_transceiver"]
    early_rmse = early_raw["rmse"]
    final_rmse = final_raw["rmse"]
    fixed_wave_improvement = None
    if early_rmse is not None and final_rmse is not None:
        fixed_wave_improvement = {
            "early_rmse": float(early_rmse),
            "final_rmse": float(final_rmse),
            "rmse_delta_early_minus_final": float(early_rmse - final_rmse),
            "improved": bool(final_rmse < early_rmse),
            "criterion": "lower complete-coverage heldout RMSE on the identical raw one-field-tick world rollout",
        }

    return _temporal_jsonable(
        {
            "stage": stage,
            "law": law,
            "feature_roles": {
                "current_only": ["input"],
                "observed_history": ["input", "input_lag1", "input_lag2", "output_lag1", "offset"],
                "history_semantics": "input_lag1, input_lag2, and output_lag1 are fixed supplied sensing features from the external world; they are not discovered temporal memory",
                "offset_semantics": "offset is retained as an optional supplied world feature for the observed-history chart; current_only is strictly current input only",
                "closed_loop_semantics": "one observed pre-probe output initializes the rollout; subsequent output_lag1 inputs use prior predictions, with no later true-output feedback",
            },
            "split": {
                "training_episode_ids": [episode["episode_id"] for episode in training_episodes],
                "heldout_episode_ids": [episode["episode_id"] for episode in heldout_episodes],
                "training_seeds": training_seeds,
                "heldout_seeds": heldout_seeds,
                "training_world_sha256": training_world_hash,
                "heldout_world_sha256": heldout_world_hash,
                "disjoint_seed_sets": True,
                "heldout_probe_ids_reused_across_checkpoints": True,
            },
            "training_episodes": training_episodes,
            "heldout_episodes": heldout_episodes,
            "training_observation_rows": training_rows,
            "heldout_observation_rows": heldout_rows,
            "admissions": admissions,
            "milestones": milestones,
            "presentation_order_sensitivity_same_world": order_results,
            "pulse_order_response_same_law": _temporal_pulse_comparison(
                session, law, current_spec, history_spec, heldout_episodes,
            ),
            "fixed_raw_wave_dynamics_training_measurement": fixed_wave_improvement,
            "budgets": {
                "conditional_prediction_ticks": int(session.default_ticks),
                "raw_one_field_tick_ticks": 1,
                "conditional_and_raw_are_reported_separately": True,
            },
            "targets_are_external_measurements": True,
            "learning_path": "all learning occurs through CurriculumSession.admit; evaluate is read-only",
            "untrained_prior_is_diagnostic_only": True,
        }
    )


def revision_retention_curriculum(
    session: CurriculumSession,
    rng: np.random.Generator,
    retained_specs: tuple[InstrumentSpec, ...],
    retained_probes: Mapping[str, list[dict]],
) -> Mapping[str, Any]:
    """Measure revision, contextual drift, guarded exceptions, and retention.

    The caller owns the three retained instruments and their held-out probes.  This
    stage admits only externally generated, controlled observations for newly
    configured charts; held-out probes are used only by ``evaluate``.
    """

    require(len(retained_specs) == 3, "revision retention requires three retained instruments")


    def _inputs(spec: InstrumentSpec, value: float) -> dict[str, float]:
        # ``bias`` is a declared constant coordinate, never a driven input.
        return {
            role: float(value)
            for role in spec.input_names
            if role != "bias"
        }

    def _hashes(specs: tuple[InstrumentSpec, ...] | list[InstrumentSpec]) -> dict[str, str]:
        return {spec.name: session.chart_identity(spec) for spec in specs}

    retained_probe_rows = {
        spec.name: retained_probes[spec.name]
        for spec in retained_specs
    }
    supplied_partition = [
        {
            "name": spec.name,
            "chart_hash": session.chart_identity(spec),
            "probe_ids": [str(row["id"]) for row in retained_probe_rows[spec.name]],
            "partition": "caller-supplied-heldout",
        }
        for spec in retained_specs
    ]
    supplied_partition_hash = sha256_value(supplied_partition)

    def _evaluate_retained(label: str) -> dict[str, Any]:
        return {
            spec.name: session.evaluate(
                spec,
                retained_probe_rows[spec.name],
                label=f"revision-retention:{label}:{spec.name}",
            )
            for spec in retained_specs
        }

    usage_before = session.usage()
    retained_hash_before = _hashes(retained_specs)
    retained_baseline = _evaluate_retained("baseline")

    # The untouched chart is deliberately unrelated to both the drift and the
    # exception streams.  Its identity is an exact chart-state control, not a
    # task-performance claim.
    refresh = session.configure(
        "revision_retention_refresh",
        input_names=("input",),
        context={"mechanism": "connected", "regime": "refresh"},
        learning_mode="stationary",
    )
    untouched = session.configure(
        "revision_retention_untouched",
        input_names=("input",),
        context={"mechanism": "connected", "regime": "untouched"},
        learning_mode="stationary",
    )
    stationary = session.configure(
        "revision_retention_drift_stationary",
        input_names=("input",),
        context={"mechanism": "connected", "regime": "changing-stream"},
        learning_mode="stationary",
    )
    contextual = session.configure(
        "revision_retention_drift_contextual",
        input_names=("input",),
        context={"mechanism": "connected", "regime": "changing-stream"},
        learning_mode="contextual",
        recency_half_life=8.0,
    )
    exception_normal = session.configure(
        "revision_retention_exception_normal",
        input_names=("input",),
        context={"mechanism": "connected", "regime": "normal"},
        learning_mode="stationary",
    )
    exception_case = session.configure(
        "revision_retention_exception_case",
        input_names=("input",),
        context={"mechanism": "connected", "regime": "exception"},
        learning_mode="stationary",
    )

    new_specs = (refresh, untouched, stationary, contextual, exception_normal, exception_case)
    configured_hashes = _hashes(list(new_specs))
    admitted_ids: list[str] = []
    admitted_by_chart: dict[str, int] = {}
    admitted_by_stage: dict[str, int] = {}

    def _admit(
        spec: InstrumentSpec,
        inputs: dict[str, float],
        target: float,
        *,
        record_id: str,
        stage: str,
        regime: str,
    ) -> None:
        session.admit(
            spec,
            inputs,
            float(target),
            record_id=record_id,
            metadata={
                "split": "train",
                "stage": stage,
                "regime": regime,
                "source": "externally-grounded-controlled-observation",
            },
        )
        admitted_ids.append(record_id)
        admitted_by_chart[spec.name] = admitted_by_chart.get(spec.name, 0) + 1
        admitted_by_stage[stage] = admitted_by_stage.get(stage, 0) + 1

    # Fixed, externally controlled old/new laws.  The same x values and targets
    # are sent to stationary and contextual charts; only chart learning mode
    # differs.  No historical observation is retracted or corrected.
    stream_x = [float(value) for value in rng.uniform(-1.0, 1.0, size=16)]
    old_targets = [1.35 * value + 0.25 for value in stream_x]
    new_targets = [-0.75 * value + 1.05 for value in stream_x]
    exception_x = [float(value) for value in rng.uniform(-1.0, 1.0, size=16)]
    normal_targets = [0.9 * value + 0.2 for value in exception_x]
    exception_targets = [-1.1 * value + 0.8 for value in exception_x]
    # These points are generated independently and are never admitted.  They
    # are reused before/after the corresponding change as fixed holdouts.
    drift_holdout_x = [float(value) for value in rng.uniform(-1.0, 1.0, size=6)]
    drift_holdout_targets = [-0.75 * value + 1.05 for value in drift_holdout_x]
    exception_holdout_x = [float(value) for value in rng.uniform(-1.0, 1.0, size=6)]
    exception_holdout_normal = [0.9 * value + 0.2 for value in exception_holdout_x]
    exception_holdout_case = [-1.1 * value + 0.8 for value in exception_holdout_x]

    for index, (value, target) in enumerate(zip(stream_x, old_targets)):
        inputs_stationary = _inputs(stationary, value)
        inputs_contextual = _inputs(contextual, value)
        _admit(
            stationary,
            inputs_stationary,
            target,
            record_id=f"revision-retention:drift:old:stationary:{index:02d}",
            stage="drift-old-regime",
            regime="old",
        )
        _admit(
            contextual,
            inputs_contextual,
            target,
            record_id=f"revision-retention:drift:old:contextual:{index:02d}",
            stage="drift-old-regime",
            regime="old",
        )
    # Exception diagnostics start before any exception observations.  This is a
    # genuine prior baseline rather than a duplicate evaluation after learning.
    exception_probes_normal = [
        {
            "id": f"revision-retention:exception-normal-probe:{index:02d}",
            "inputs": _inputs(exception_normal, value),
            "target": float(target),
        }
        for index, (value, target) in enumerate(
            zip(exception_holdout_x, exception_holdout_normal)
        )
    ]
    exception_probes_case = [
        {
            "id": f"revision-retention:exception-case-probe:{index:02d}",
            "inputs": _inputs(exception_case, value),
            "target": float(target),
        }
        for index, (value, target) in enumerate(
            zip(exception_holdout_x, exception_holdout_case)
        )
    ]
    exception_baseline = {
        "normal": session.evaluate(
            exception_normal,
            exception_probes_normal,
            label="revision-retention:exception:normal-before-learning",
        ),
        "exception": session.evaluate(
            exception_case,
            exception_probes_case,
            label="revision-retention:exception:case-before-learning",
        ),
    }
    for index, (value, normal_target, exception_target) in enumerate(
        zip(exception_x, normal_targets, exception_targets)
    ):
        _admit(
            exception_normal,
            _inputs(exception_normal, value),
            normal_target,
            record_id=f"revision-retention:exception:normal:{index:02d}",
            stage="exception-training",
            regime="normal",
        )
        _admit(
            exception_case,
            _inputs(exception_case, value),
            exception_target,
            record_id=f"revision-retention:exception:case:{index:02d}",
            stage="exception-training",
            regime="exception",
        )

    drift_new_probes = [
        {
            "id": f"revision-retention:drift-new-probe:{index:02d}",
            "inputs": _inputs(stationary, value),
            "target": float(target),
        }
        for index, (value, target) in enumerate(
            zip(drift_holdout_x, drift_holdout_targets)
        )
    ]
    drift_before = {
        "stationary": session.evaluate(
            stationary,
            drift_new_probes,
            label="revision-retention:drift:new-before",
        ),
        "contextual": session.evaluate(
            contextual,
            [
                {
                    **probe,
                    "inputs": _inputs(contextual, drift_holdout_x[index]),
                }
                for index, probe in enumerate(drift_new_probes)
            ],
            label="revision-retention:drift:new-before-contextual",
        ),
    }

    # New-regime observations are interleaved with refresh observations for a
    # genuinely unrelated chart.  This makes the refresh a retention pressure,
    # while keeping every source and target explicit and independently hashed.
    for index, (value, target) in enumerate(zip(stream_x, new_targets)):
        _admit(
            refresh,
            _inputs(refresh, value),
            0.42 * value - 0.15,
            record_id=f"revision-retention:refresh:{index:02d}",
            stage="interleaved-unrelated-refresh",
            regime="refresh",
        )
        _admit(
            stationary,
            _inputs(stationary, value),
            target,
            record_id=f"revision-retention:drift:new:stationary:{index:02d}",
            stage="drift-new-regime",
            regime="new",
        )
        _admit(
            contextual,
            _inputs(contextual, value),
            target,
            record_id=f"revision-retention:drift:new:contextual:{index:02d}",
            stage="drift-new-regime",
            regime="new",
        )

    drift_after = {
        "stationary": session.evaluate(
            stationary,
            drift_new_probes,
            label="revision-retention:drift:new-after",
        ),
        "contextual": session.evaluate(
            contextual,
            [
                {
                    **probe,
                    "inputs": _inputs(contextual, drift_holdout_x[index]),
                }
                for index, probe in enumerate(drift_new_probes)
            ],
            label="revision-retention:drift:new-after-contextual",
        ),
    }

    exception_after = {
        "normal": session.evaluate(
            exception_normal,
            exception_probes_normal,
            label="revision-retention:exception:normal-after-change",
        ),
        "exception": session.evaluate(
            exception_case,
            exception_probes_case,
            label="revision-retention:exception:case-after-change",
        ),
    }

    retained_after = _evaluate_retained("after-unrelated-learning")
    restart_inputs = (
        dict(retained_probe_rows[retained_specs[0].name][0]["inputs"])
        if retained_probe_rows[retained_specs[0].name]
        else _inputs(retained_specs[0], 0.0)
    )
    restart_result: Mapping[str, Any] = session.restart_probe(
        retained_specs[0], restart_inputs
    )

    # Route an unknown context through the canonical owner, not through a
    # bypass InstrumentSpec.  Exception/normal evaluation above has condensed
    # their transceivers; this operation must therefore refuse applicability
    # without publishing a successor state.
    unknown_context = {**exception_normal.context, "regime": "unknown"}
    unknown_owner_before = session.owner.state.state_sha256
    unknown_usage_before = session.usage()
    unknown_hashes_before = _hashes(
        [exception_normal, exception_case, refresh, untouched]
    )
    unknown_result: Mapping[str, Any] | None = None
    try:
        session.owner.advance_transceivers(
            "revision:unknown-context",
            stimuli={
                exception_normal.name: {
                    exception_normal.variable("input"): 0.5,
                }
            },
            context=unknown_context,
        )
    except FieldIntelligenceError as exc:
        unknown_result = {
            "operation_id": "revision:unknown-context",
            "context": unknown_context,
            "status": "refused",
            "refused": True,
            "error": f"{type(exc).__name__}: {exc}",
            "error_code": exc.code,
        }
        require(
            exc.code == "TRANSCEIVER_INAPPLICABLE",
            f"unknown context refusal returned unexpected code {exc.code!r}",
        )
    else:
        require(
            False,
            "unknown context unexpectedly advanced a condensed transceiver",
        )
    unknown_owner_after = session.owner.state.state_sha256
    unknown_usage_after = session.usage()
    unknown_hashes_after = _hashes(
        [exception_normal, exception_case, refresh, untouched]
    )
    require(
        unknown_owner_before == unknown_owner_after,
        "unknown context refusal changed canonical owner state",
    )
    require(
        sha256_value(unknown_usage_before) == sha256_value(unknown_usage_after),
        "unknown context refusal changed usage",
    )
    require(
        unknown_hashes_before == unknown_hashes_after,
        "unknown context refusal changed known chart identity",
    )
    require(
        unknown_result is not None,
        "unknown context operation returned without a refusal result",
    )
    unknown_result = {
        **(unknown_result or {}),
        "owner_state_before": unknown_owner_before,
        "owner_state_after": unknown_owner_after,
        "state_unchanged_after_failed_operation": True,
        "usage_unchanged_after_failed_operation": True,
        "known_chart_hashes_unchanged": True,
    }

    usage_after = session.usage()
    final_hashes = _hashes(tuple(retained_specs) + tuple(new_specs))
    retained_hash_after = {spec.name: final_hashes[spec.name] for spec in retained_specs}
    untouched_hash_before = configured_hashes[untouched.name]
    untouched_hash_after = final_hashes[untouched.name]
    diagnostic_ids = [
        *(str(row["id"]) for row in drift_new_probes),
        *(str(row["id"]) for row in exception_probes_normal),
        *(str(row["id"]) for row in exception_probes_case),
    ]
    supplied_heldout_ids = {
        probe_id
        for rows in retained_probe_rows.values()
        for probe_id in (str(row["id"]) for row in rows)
    }
    heldout_ids = supplied_heldout_ids | set(diagnostic_ids)
    admitted_id_set = set(admitted_ids)

    return {
        "stage": "revision_retention",
        "retained": {
            "baseline": retained_baseline,
            "after": retained_after,
            "chart_hashes": {
                "before": retained_hash_before,
                "after": retained_hash_after,
                "exact_identity_unchanged": {
                    name: retained_hash_before[name] == retained_hash_after[name]
                    for name in retained_hash_before
                },
            },
            "supplied_chart_partition": supplied_partition,
            "supplied_chart_partition_sha256": supplied_partition_hash,
        },
        "changing_environment": {
            "stationary": {
                "chart_hash": configured_hashes[stationary.name],
                "new_regime_before_change": drift_before["stationary"],
                "new_regime_after_change": drift_after["stationary"],
            },
            "contextual_recency": {
                "chart_hash": configured_hashes[contextual.name],
                "recency_half_life": 8.0,
                "new_regime_before_change": drift_before["contextual"],
                "new_regime_after_change": drift_after["contextual"],
            },
            "identical_observation_values": sha256_value(
                [
                    {"input": value, "old_target": old, "new_target": new}
                    for value, old, new in zip(stream_x, old_targets, new_targets)
                ]
            ),
            "historical_sources_retracted": False,
            "source_correction_called": False,
        },
        "exception": {
            "normal": exception_baseline["normal"],
            "exception": exception_baseline["exception"],
            "after_normal": exception_after["normal"],
            "after_exception": exception_after["exception"],
            "guards": {
                "normal": {
                    "identity": sha256_value(exception_normal.context),
                    "routing": "supplied normal-context guard; not learned",
                },
                "exception": {
                    "identity": sha256_value(exception_case.context),
                    "routing": "supplied exception-context guard; not learned",
                },
            },
            "unknown_context": unknown_result,
        },
        "restart": restart_result,
        "source_counts": {
            "admitted_total": len(admitted_ids),
            "admitted_by_chart": dict(admitted_by_chart),
            "admitted_by_stage": dict(admitted_by_stage),
            "heldout_probe_count": len(heldout_ids),
            "supplied_heldout_probe_count": len(supplied_heldout_ids),
            "diagnostic_heldout_probe_count": len(diagnostic_ids),
            "heldout_ids_disjoint_from_stage_sources": not bool(heldout_ids & admitted_id_set),
            "heldout_id_sha256": sha256_value(sorted(heldout_ids)),
            "admitted_record_id_sha256": sha256_value(sorted(admitted_ids)),
        },
        "identity_checks": {
            "untouched_unrelated_chart_hash_before": untouched_hash_before,
            "untouched_unrelated_chart_hash_after": untouched_hash_after,
            "untouched_unrelated_chart_exactly_unchanged": untouched_hash_before
            == untouched_hash_after,
            "retained_task_metrics_are_separate_from_chart_identity": True,
            "supplied_partition_is_separate_from_admitted_sources": not bool(
                heldout_ids & admitted_id_set
            ),
            "selected_chart_hashes_after": final_hashes,
        },
        "usage": {
            "before": usage_before,
            "after": usage_after,
            "current": usage_after,
        },
    }


def _write_curriculum_report(output: Path, report: Mapping[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_suffix(output.suffix + ".partial")
    staging.write_bytes(canonical_json_bytes(report))
    staging.replace(output)


def _curriculum_summary(row: Mapping[str, Any]) -> Mapping[str, Any]:
    temporal = row["temporal"]["milestones"][-1]
    revision = row["revision_retention"]
    return {
        "seed": row["seed"],
        "affine_final_rmse": {
            name: {condition: result["rmse"] for condition, result in result["conditions"].items()}
            for name, result in row["affine"]["learning_curve"][-1]["evaluations"].items()
        },
        "composition_rmse": row["composition"]["rmse"],
        "temporal_final_rmse": {
            name: {condition: value["rmse"] for condition, value in temporal[name]["conditions"].items()}
            for name in (
                "current_only_carried_transceiver_64tick",
                "observed_history_conditional_true_past_64tick",
                "observed_history_closed_loop_predicted_past_64tick",
                "raw_current_only_fixed_wave_one_field_tick",
            )
        },
        "new_regime_rmse": {
            mode: {
                when: revision["changing_environment"][mode][f"new_regime_{when}_change"]
                ["conditions"]["trained_transceiver"]["rmse"]
                for when in ("before", "after")
            } for mode in ("stationary", "contextual_recency")
        },
        "retained_chart_identity_unchanged": revision["retained"]["chart_hashes"]["exact_identity_unchanged"],
        "usage": row["usage"], "costs": row["costs"],
        "elapsed_seconds": row["elapsed_seconds"],
    }


def run_curriculum(
    home: Path, output: Path, *, seeds: list[int], samples: int = 32, ticks: int = 64,
) -> Mapping[str, Any]:
    require(4 <= samples <= 256, "training samples must be in [4,256]")
    require(1 <= ticks <= 64, "field ticks per prediction must be in [1,64]")
    require(bool(seeds) and len(seeds) == len(set(seeds)) and
            all(0 <= seed < 2**32 for seed in seeds), "seeds must be unique uint32 values")
    require(not output.exists(), f"report already exists: {output}")
    require(not home.exists() or not any(home.iterdir()), f"data home is not empty: {home}")
    source_root = Path(__file__).resolve().parent
    sources = (
        Path(__file__).name, "cassi_field_atlas.py", "cassi_field_owner.py",
        "cassi_field_cognition.py", "cassi_variational_field.py",
        "cassi_resonant_field.py", "cassi_field_transceiver.py",
    )
    report: dict[str, Any] = {
        "schema": "cassifi.field-training-curriculum.v1",
        "execution_status": "running", "seeds": seeds,
        "configuration": {
            "affine_training_samples_per_instrument": samples, "internal_ticks_per_prediction": ticks,
            "compact_rank": 16, "compact_error_allowance": 1e-3,
            "input_bound": 8.0, "compact_horizon_ticks": 4096,
            "task_success_absolute_error": 0.05,
            "profile": ResonantProfile(beta=0.0, damping=0.5).as_dict(),
        },
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "numpy": np.__version__, "torch": torch.__version__, "torch_threads": torch.get_num_threads(),
        },
        "source_sha256": {name: hashlib.sha256((source_root/name).read_bytes()).hexdigest()
                          for name in sources},
        "scope": {
            "training": "structured observations from independently specified controlled worlds",
            "adaptive_owner": "canonical field charts only",
            "evaluation": "immutable numerical forks; composition and restart use actual owner publication",
            "untrained": "production condensation refuses zero support; raw prior numbers are diagnostic only",
            "task_rmse": "external target error, separate from compact/full numerical agreement",
            "success_fraction": "all-probe absolute error <=0.05; missing predictions count as failures",
            "supplied": ["variables", "chart scopes", "context guards", "port roles",
                         "composition wiring", "observed-history sensing features"],
            "cost_boundary": "setup, admissions, compilation, numerical evaluation, owner publication, retained disk",
            "timing": "single-process CPU runs; not a general speedup estimate",
        },
        "data_home": str(home.resolve()), "runs": [], "summaries": [],
    }
    started = perf_counter()
    _write_curriculum_report(output, report)
    for seed in seeds:
        session = CurriculumSession(home/f"seed-{seed}", seed=seed, ticks=ticks)
        row: dict[str, Any] = {"seed": seed, "execution_status": "running"}
        report["runs"].append(row)
        seed_started = perf_counter()
        try:
            stage_rngs = [np.random.default_rng(child) for child in
                          np.random.SeedSequence(seed).spawn(3)]
            affine, specs, probes = affine_curriculum(session, stage_rngs[0], samples=samples)
            row["affine"] = affine
            _write_curriculum_report(output, report)
            row["composition"] = composition_curriculum(session, specs, affine["laws"])
            _write_curriculum_report(output, report)
            print(json.dumps({"stage": "composition", "seed": seed,
                              "rmse": row["composition"]["rmse"]}), flush=True)
            row["temporal"] = temporal_curriculum(session, stage_rngs[1])
            _write_curriculum_report(output, report)
            print(json.dumps({"stage": "temporal", "seed": seed, "completed": True}), flush=True)
            row["revision_retention"] = revision_retention_curriculum(
                session, stage_rngs[2], specs, probes,
            )
            row["builds"] = session.builds
            row["untrained_production_refusals"] = session.refusals
            row["data_identity"] = {
                "training_sources": session.training_sources,
                "training_records_sha256": sha256_value(sorted(session.training_hashes)),
                "heldout_records_sha256": sha256_value(sorted(session.heldout_hashes)),
                "training_unique_records": len(session.training_hashes),
                "heldout_unique_records": len(session.heldout_hashes),
                "overlap_count": len(session.training_hashes & session.heldout_hashes),
            }
            require(row["data_identity"]["overlap_count"] == 0, "training/heldout leakage")
            row["usage"], row["costs"] = session.usage(), dict(session.costs)
            row["state_sha256"] = session.owner.state.state_sha256
            row["manifest_sha256"] = session.owner.checkpoints.current_manifest_sha256
            row["live_model_calls"] = 0
            row["elapsed_seconds"] = perf_counter() - seed_started
            row["execution_status"] = "completed"
            summary = _curriculum_summary(row)
            report["summaries"].append(summary)
            print(json.dumps(summary, allow_nan=False), flush=True)
        except Exception as exc:
            row["execution_status"] = "interrupted"
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
            report["execution_status"] = "interrupted"
            _write_curriculum_report(output, report)
            raise
        finally:
            session.owner.close()
        _write_curriculum_report(output, report)
    report["execution_status"] = "completed"
    report["elapsed_seconds"] = perf_counter() - started
    _write_curriculum_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--curriculum", action="store_true",
                        help="run sustained training with retained isolated owners and heldout evaluation")
    parser.add_argument("--data-home", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--ticks", type=int, default=64)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.curriculum:
        output = args.output or Path("_diag/field-curriculum/report.json")
        home = args.data_home or output.parent/"owners"
        report = run_curriculum(
            home, output, seeds=args.seeds, samples=args.samples, ticks=args.ticks,
        )
        print(json.dumps({
            "execution_status": report["execution_status"], "report": str(output),
            "data_home": str(home), "seeds": args.seeds,
            "elapsed_seconds": report["elapsed_seconds"],
        }), flush=True)
    else:
        output = args.output or Path("_diag/field-transceivers/scenario.json")
        with tempfile.TemporaryDirectory(prefix="cassi-transceivers-") as temporary:
            root = Path(temporary)
            report = {
                "schema": "cassifi.field-transceiver-scenario.v1",
                "scope": "controlled instrument relations, temporal full-field equivalence, canonical owner lifecycle",
                "linear": numerical_scenario(root / "linear", beta=0.0),
                "nonlinear": numerical_scenario(root / "nonlinear", beta=0.08),
                "owner": owner_scenario(root / "owner"),
            }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(canonical_json_bytes(report))
        print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
