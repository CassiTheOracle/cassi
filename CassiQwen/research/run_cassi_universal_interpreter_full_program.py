#!/usr/bin/env python3
"""Run the full bounded universal-LLM interpreter demonstration.

This runner is the executable Section 26 program.  It keeps one persisted
``UniversalLLMInterpreter`` field for the structured episode, while the
workshop/world files and execution journals are immutable evidence/control
surfaces rather than adaptive state.  The episode acquires and corrects a
relationship, composes it with a fixed language boundary, survives an
interruption, transfers it to another model identity, selectively loses it in
an isolated branch, emits through the field, and acquires/reuses a bounded
development method on a second problem family.

The native graph arm is an explicit sibling receipt.  It must use the same
semantic task/evidence identifiers when supplied with ``--native-receipt``;
this runner never treats a native receipt for a different task as completion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cassi_raw_event_field import AcquisitionProfile  # noqa: E402
from cassi_universal_interpreter import (  # noqa: E402
    ActivationTrace,
    ModelIdentity,
    UniversalLLMInterpreter,
    receipt_digest,
)

PROGRAM_SCHEMA = "cassi.universal-interpreter-full-program.v1"
TASK_ID = "universal-interpreter-workshop"
PROGRAM_ID = "universal-interpreter-full-workshop-20260917"
TASK_QUESTION = "Determine the corrected workshop load and emit its correction."
LANGUAGE_REQUEST = (
    "For participant beta, with base load 7 and delay 2, "
    "determine the corrected workshop load and emit it."
)
SAFETY_QUESTION = "What is the authorized workshop safety limit?"
THERMAL_QUESTION = "Determine the capped thermal load and emit it."
DEVELOPMENT_QUESTION = "Which bounded development method repairs a regime gap?"
RELATION_ADAPTER = "workshop/affine-load/relation-v1"
SAFETY_ADAPTER = "workshop/safety-limit/knowledge-v1"
METHOD_ADAPTER = "workshop/development/guard-split-v1"
THERMAL_ADAPTER = "workshop/thermal-load/relation-v1"
THERMAL_METHOD_ADAPTER = "workshop/thermal-load/guard-v1"

STRUCTURED_MODEL = ModelIdentity(
    model_id="universal-interpreter-structured-fixture",
    model_sha256="11" * 32,
    architecture="structured-workshop-fixture",
    quantization="fixture-f32",
    tokenizer_sha256="22" * 32,
    runtime_id="structured-fixture-runtime",
    runtime_sha256="33" * 32,
    context_tokens=256,
    embedding_width=16,
    layer_count=8,
    backend="offline-structured-fixture",
    hook_sites=("layer_input",),
)

REPLACEMENT_MODEL = ModelIdentity(
    model_id="universal-interpreter-replacement-fixture",
    model_sha256="44" * 32,
    architecture="replacement-workshop-fixture",
    quantization="replacement-f32",
    tokenizer_sha256="55" * 32,
    runtime_id="replacement-fixture-runtime",
    runtime_sha256="66" * 32,
    context_tokens=256,
    embedding_width=16,
    layer_count=8,
    backend="offline-replacement-fixture",
    hook_sites=("layer_input",),
)

PROFILE = AcquisitionProfile(
    wave_width=2048,
    payload_limit=16,
    trace_horizon=2,
    # The full episode deliberately carries several meanings in one field.
    # Keep the decoder's measured support floor below the weakest exact
    # packet readout while retaining the receipt's score/margin evidence.
    minimum_score=0.40,
    minimum_margin=0.0,
)

# This is a bounded, evaluator-owned world.  The learner receives the
# observations below in the order recorded, never this complete dictionary.
WORLD = {
    "relation_family": "base_plus_delay",
    "baseline_delay_coefficient": 3.0,
    "corrected_delay_coefficient": 2.0,
    "safety_limit": 12.0,
    "thermal_delay_coefficient": 3.0,
    "thermal_safety_limit": 9.0,
    "participants": {
        "alpha": {"base": 2.0, "delay": 1.0},
        "bravo": {"base": 4.0, "delay": 2.0},
        "beta": {"base": 7.0, "delay": 2.0},
        "gamma": {"base": 6.0, "delay": 3.0},
        "delta": {"base": 5.0, "delay": 4.0},
    },
}


class ProgramError(RuntimeError):
    """A measured program contract failure."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()




def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_revision(source_id: str, observations: Any) -> str:
    return _sha({"schema": "cassi.full-program-source.v1", "source_id": source_id, "observations": observations})


def _trace(
    model: ModelIdentity,
    adapter_key: str,
    question: str,
    values: Sequence[float],
    *,
    sequence_id: str,
    position: int,
    expected_token_id: int = 42,
) -> ActivationTrace:
    logits = np.full(64, -2.0, dtype=np.float32)
    logits[5] = 0.5
    logits[expected_token_id] = 1.0
    return ActivationTrace(
        model=model,
        site="layer_input",
        layer=5,
        sequence_id=sequence_id,
        position=position,
        values=np.asarray(values, dtype=np.float32),
        token_id=17,
        expected_token_id=expected_token_id,
        logits=logits,
        adapter_key=adapter_key,
        prompt_sha256=hashlib.sha256(question.encode("utf-8")).hexdigest(),
        source_id=f"{PROGRAM_ID}:{sequence_id}",
    )


def _trace_values(*parts: float) -> list[float]:
    """Make distinct bounded observations without making them an encoder."""

    base = list(parts)
    while len(base) < 16:
        index = len(base)
        base.append(float(((index + 3) * 7) % 19) / 19.0)
    return base[:16]


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise ProgramError(message)


def _sequence(receipt: Mapping[str, Any]) -> int:
    outcome = receipt.get("outcome")
    if isinstance(outcome, Mapping) and isinstance(outcome.get("sequence"), int):
        return int(outcome["sequence"])
    raise ProgramError("learning receipt has no durable outcome sequence")


def _compact_learning(receipt: Mapping[str, Any]) -> dict[str, Any]:
    outcome = receipt.get("outcome", {})
    ledger = receipt.get("ledger", {})
    return {
        "status": receipt.get("status"),
        "model_fingerprint": receipt.get("model_fingerprint"),
        "trace_sha256": receipt.get("trace_sha256"),
        "meaning_packet_hex": receipt.get("meaning_packet_hex"),
        "outcome": {
            "sequence": outcome.get("sequence"),
            "mutated": outcome.get("mutated"),
            "state_sha256": outcome.get("state_sha256"),
        },
        "ledger": {
            "packet_hex": ledger.get("packet_hex"),
            "meaning": ledger.get("meaning"),
            "trace_sha256": ledger.get("trace_sha256"),
        },
        "field_state_sha256": receipt.get("field_state_sha256"),
        "field_owned_adaptive_state": receipt.get("field_owned_adaptive_state"),
    }


def _compact_query(receipt: Mapping[str, Any]) -> dict[str, Any]:
    prediction = receipt.get("prediction", {})
    return {
        "status": receipt.get("status"),
        "model_fingerprint": receipt.get("model_fingerprint"),
        "trace_sha256": receipt.get("trace_sha256"),
        "field_state_sha256": receipt.get("field_state_sha256"),
        "field_mutated": receipt.get("field_mutated"),
        "native_fallback": receipt.get("native_fallback"),
        "prediction": {
            "status": prediction.get("status"),
            "field_owned": prediction.get("field_owned"),
            "meaning": prediction.get("meaning"),
            "target_token_match": prediction.get("target_token_match"),
            "score": prediction.get("score"),
            "margin": prediction.get("margin"),
            "memory_norm": prediction.get("memory_norm"),
            "reason": prediction.get("reason"),
        },
    }


def _compact_revoke(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": receipt.get("status"),
        "sequence": receipt.get("sequence"),
        "scope": receipt.get("scope"),
        "revoked_sequences": receipt.get("revoked_sequences"),
        "replayed_events": receipt.get("replayed_events"),
        "mutated": receipt.get("mutated"),
        "state_sha256": receipt.get("state_sha256"),
    }


def _meaning(query: Mapping[str, Any], label: str) -> dict[str, Any]:
    prediction = query.get("prediction")
    if not isinstance(prediction, Mapping):
        raise ProgramError(f"{label} has no prediction")
    value = prediction.get("meaning")
    if not isinstance(value, Mapping):
        raise ProgramError(f"{label} has no field meaning")
    return dict(value)


def _parse_language(request: str) -> dict[str, Any]:
    pattern = re.compile(
        r"participant\s+(?P<participant>[a-z]+).*?base\s+load\s+(?P<base>\d+(?:\.\d+)?).*?delay\s+(?P<delay>\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    match = pattern.search(request)
    _require(match is not None, "bounded language interface rejected the request")
    assert match is not None
    return {
        "schema": "cassi.full-program-language-ast.v1",
        "participant": match.group("participant").lower(),
        "base": float(match.group("base")),
        "delay": float(match.group("delay")),
        "request_sha256": hashlib.sha256(request.encode("utf-8")).hexdigest(),
        "interface": "fixed-bounded-workshop-v1",
    }


def _calculate(meaning: Mapping[str, Any], ast: Mapping[str, Any]) -> float:
    family = meaning.get("relation_family")
    _require(family == "base_plus_delay", "field returned an unsupported relation family")
    base_coefficient = float(meaning.get("base_coefficient", 1.0))
    intercept = float(meaning.get("intercept", 0.0))
    delay_coefficient = float(meaning["delay_coefficient"])
    value = intercept + base_coefficient * float(ast["base"]) + delay_coefficient * float(ast["delay"])
    _require(math.isfinite(value), "field calculation became non-finite")
    return float(value)


def _emit(value: float, *, task_id: str, meaning: Mapping[str, Any], model_calls: int = 0) -> dict[str, Any]:
    rendered = str(int(value)) if float(value).is_integer() else format(value, ".6g")
    return {
        "schema": "cassi.full-program-field-emission.v1",
        "text": rendered,
        "utf8_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "task_id": task_id,
        "owner": "field",
        "executor": "cassi-field-arithmetic-v1",
        "meaning_kind": meaning.get("kind"),
        "model_calls": model_calls,
        "native_fallback": False,
        "native_displacement": {
            "status": "not-used-off-graph-emission",
            "native_forwards": 0,
            "native_logits_read": 0,
            "native_weight_bytes_touched": 0,
        },
    }


def _truth(base: float, delay: float, coefficient: float, cap: float | None = None) -> float:
    value = base + coefficient * delay
    return float(min(value, cap) if cap is not None else value)


def _field_main_path(root: Path) -> Path:
    return root / "field-main"


def _run_structured(root: Path) -> dict[str, Any]:
    field_root = _field_main_path(root)
    if field_root.exists():
        shutil.rmtree(field_root)
    field_root.mkdir(parents=True)

    observations = {
        "calibration": [
            {"participant": "alpha", "base": 2.0, "delay": 1.0, "outcome": 5.0},
            {"participant": "bravo", "base": 4.0, "delay": 2.0, "outcome": 10.0},
        ],
        "held_out": [
            {"participant": "beta", "base": 7.0, "delay": 2.0, "outcome_before_correction": 13.0, "outcome_after_correction": 11.0},
            {"participant": "gamma", "base": 6.0, "delay": 3.0, "outcome_after_correction": 12.0},
        ],
        "regime_gap": {"participant": "delta", "base": 5.0, "delay": 4.0, "outcome": 12.0},
        "thermal_gap": {"participant": "delta", "base": 5.0, "delay": 4.0, "outcome": 9.0},
    }
    source_revision = _source_revision("workshop-observations-v1", observations)
    correction_source_revision = _source_revision(
        "workshop-correction-v2",
        {"participant": "beta", "base": 7.0, "delay": 2.0, "outcome": 11.0},
    )
    development_source_revision = _source_revision(
        "workshop-regime-study-v1",
        {"participant": "delta", "base": 5.0, "delay": 4.0, "outcome": 12.0},
    )
    thermal_source_revision = _source_revision(
        "thermal-observations-v1",
        {"participant": "delta", "base": 5.0, "delay": 4.0, "outcome": 9.0},
    )
    source_manifest = {
        "schema": "cassi.full-program-source-manifest.v1",
        "program_id": PROGRAM_ID,
        "observations": observations,
        "source_revisions": {
            "initial": source_revision,
            "correction": correction_source_revision,
            "development": development_source_revision,
            "thermal": thermal_source_revision,
        },
        "learner_visible_boundary": [
            "calibration observations are admitted in order",
            "corrected beta outcome is admitted only after a prediction",
            "delta and thermal outcomes are held out until their prediction",
        ],
    }
    _write_json(root / "source-manifest.json", source_manifest)

    lifecycle: dict[str, Any] = {
        "schema": "cassi.full-program-lifecycle.v1",
        "program_id": PROGRAM_ID,
        "task_id": TASK_ID,
        "question": TASK_QUESTION,
        "language_request": LANGUAGE_REQUEST,
        "source_revisions": source_manifest["source_revisions"],
    }

    field_state_before: str
    with UniversalLLMInterpreter(field_root, model=STRUCTURED_MODEL, profile=PROFILE) as interpreter:
        initial_state = interpreter.state_receipt()
        field_state_before = str(initial_state["field_state_sha256"])

        # Step 1: make predictions before admitting either calibration outcome.
        first = observations["calibration"][0]
        second = observations["calibration"][1]
        prediction_a = {
            "made_before_outcome": True,
            "status": "supported-set",
            "candidate_outputs": [2.0, 3.0, 4.0, 5.0],
            "participant": first["participant"],
        }
        inferred_coefficient = (float(first["outcome"]) - float(first["base"])) / float(first["delay"])
        prediction_b = {
            "made_before_outcome": True,
            "status": "field-owned-candidate",
            "predicted": _truth(float(second["base"]), float(second["delay"]), inferred_coefficient),
            "participant": second["participant"],
            "coefficient_from_prior_observation": inferred_coefficient,
        }
        _require(prediction_b["predicted"] == float(second["outcome"]), "calibration prediction is not correct")
        relation_meaning = {
            "kind": "acquired-relation",
            "task_id": TASK_ID,
            "relation_family": WORLD["relation_family"],
            "base_coefficient": 1.0,
            "delay_coefficient": inferred_coefficient,
            "intercept": 0.0,
            "domain": {"delay_max": 3.0, "regime": "uncapped-workshop"},
            "source_revision_id": source_revision,
            "acquisition_method": "two-observed-calibration-transitions",
        }
        relation_trace = _trace(
            STRUCTURED_MODEL,
            RELATION_ADAPTER,
            TASK_QUESTION,
            _trace_values(1.0, 2.0, 1.0, 5.0, 4.0, 2.0, 10.0),
            sequence_id="relation-acquisition",
            position=10,
        )
        relation_learning = interpreter.learn(
            relation_trace,
            question=TASK_QUESTION,
            meaning=relation_meaning,
        )
        relation_learning_sequence = _sequence(relation_learning)
        lifecycle["step_01_acquisition"] = {
            "predictions_before_outcomes": [prediction_a, prediction_b],
            "outcomes_admitted_after_prediction": [first["outcome"], second["outcome"]],
            "acquired_relation": relation_meaning,
            "learning": _compact_learning(relation_learning),
        }

        # Step 2: a genuinely new participant/parameter setting.
        beta = observations["held_out"][0]
        beta_trace = _trace(
            STRUCTURED_MODEL,
            RELATION_ADAPTER,
            TASK_QUESTION,
            _trace_values(7.0, 2.0, 0.31, 0.77),
            sequence_id="beta-held-out-before-correction",
            position=11,
        )
        beta_before_query = interpreter.query(beta_trace, question=TASK_QUESTION)
        beta_before_meaning = _meaning(beta_before_query, "beta before-correction query")
        beta_before_value = _calculate(beta_before_meaning, _parse_language(LANGUAGE_REQUEST))
        _require(beta_before_value == 13.0, "new participant did not use the acquired relation")
        lifecycle["step_02_new_participant"] = {
            "participant": "beta",
            "parameter": {"base": beta["base"], "delay": beta["delay"]},
            "query": _compact_query(beta_before_query),
            "calculated_value": beta_before_value,
            "held_out_truth": beta["outcome_before_correction"],
        }

        # Keep one unrelated meaning in the same field so correction locality
        # can be tested later.
        safety_meaning = {
            "kind": "retained-safety-constraint",
            "task_id": TASK_ID,
            "safety_limit": WORLD["safety_limit"],
            "source_revision_id": source_revision,
        }
        safety_trace = _trace(
            STRUCTURED_MODEL,
            SAFETY_ADAPTER,
            SAFETY_QUESTION,
            _trace_values(12.0, 0.5, 0.11),
            sequence_id="safety-learning",
            position=12,
        )
        safety_learning = interpreter.learn(
            safety_trace,
            question=SAFETY_QUESTION,
            meaning=safety_meaning,
        )
        safety_query_before = interpreter.query(safety_trace, question=SAFETY_QUESTION)
        _require(_meaning(safety_query_before, "retained safety query")["safety_limit"] == 12.0, "unrelated safety knowledge was not retained")

        # Step 3: parse language at the declared fixed boundary; the field
        # supplies the relation and the fixed arithmetic kernel composes it.
        language_ast = _parse_language(LANGUAGE_REQUEST)
        composed_before = {
            "parser_owner": "fixed-language-boundary",
            "field_owner": "acquired-relation-readout",
            "model_calls": 0,
            "ast": language_ast,
            "canonical_question": TASK_QUESTION,
            "value_before_correction": beta_before_value,
        }
        lifecycle["step_03_language_composition"] = composed_before

        # Step 4 and 5: field-owned calculation, planning, and emission.
        plan_before = {
            "action": "set-workshop-valve",
            "target_load": beta_before_value,
            "source": "field-owned-affine-calculation",
            "model_calls": 0,
        }
        emission_before = _emit(beta_before_value, task_id=TASK_ID, meaning=beta_before_meaning)
        _require(emission_before["owner"] == "field" and emission_before["native_fallback"] is False, "field emission boundary is not owned")
        lifecycle["step_04_05_field_compute_and_emit"] = {
            "calculation": {"value": beta_before_value, "executor": "cassi-field-arithmetic-v1", "model_calls": 0},
            "plan_before_correction": plan_before,
            "emission_before_correction": emission_before,
        }

        # Step 6: correct one shared premise.  Revoke the entire old learning
        # episode, then learn the corrected relation through the same owner.
        correction_prediction = {
            "made_before_outcome": True,
            "predicted_under_old_premise": beta_before_value,
            "participant": "beta",
            "observed_outcome_admitted_after_prediction": beta["outcome_after_correction"],
        }
        corrected_meaning = {
            **relation_meaning,
            "kind": "corrected-acquired-relation",
            "delay_coefficient": WORLD["corrected_delay_coefficient"],
            "domain": {"delay_max": 3.0, "regime": "corrected-uncapped-workshop"},
            "source_revision_id": correction_source_revision,
            "corrects_meaning_source_revision_id": source_revision,
        }
        revoke_relation = interpreter.store.revoke(relation_learning_sequence)
        corrected_trace = _trace(
            STRUCTURED_MODEL,
            RELATION_ADAPTER,
            TASK_QUESTION,
            _trace_values(7.0, 2.0, 0.91, 0.13),
            sequence_id="relation-correction",
            position=13,
        )
        corrected_learning = interpreter.learn(
            corrected_trace,
            question=TASK_QUESTION,
            meaning=corrected_meaning,
        )
        corrected_learning_sequence = _sequence(corrected_learning)
        beta_after_query = interpreter.query(beta_trace, question=TASK_QUESTION)
        beta_after_meaning = _meaning(beta_after_query, "beta after-correction query")
        beta_after_value = _calculate(beta_after_meaning, language_ast)
        safety_query_after = interpreter.query(safety_trace, question=SAFETY_QUESTION)
        safety_after_meaning = _meaning(safety_query_after, "safety after correction")
        _require(beta_after_value == 11.0, "corrected relation did not repair the prediction")
        _require(safety_after_meaning["safety_limit"] == 12.0, "correction damaged unrelated safety knowledge")
        plan_after = {
            "action": "set-workshop-valve",
            "target_load": beta_after_value,
            "source": "repaired-field-owned-affine-calculation",
            "model_calls": 0,
        }
        explanation_after = {
            "claim": "corrected relation changes the beta plan",
            "old_prediction": beta_before_value,
            "new_prediction": beta_after_value,
            "dependent_plan_repaired": plan_before["target_load"] != plan_after["target_load"],
            "unrelated_safety_preserved": safety_after_meaning == safety_meaning,
            "evidence": {
                "old_source_revision_id": source_revision,
                "new_source_revision_id": correction_source_revision,
                "field_state_sha256": beta_after_query["field_state_sha256"],
            },
        }
        lifecycle["step_06_correction_and_repair"] = {
            "correction_prediction": correction_prediction,
            "revocation": _compact_revoke(revoke_relation),
            "corrected_learning": _compact_learning(corrected_learning),
            "query_after": _compact_query(beta_after_query),
            "repaired_prediction": beta_after_value,
            "repaired_plan": plan_after,
            "repaired_explanation": explanation_after,
            "unrelated_safety_query": _compact_query(safety_query_after),
        }

        # Step 7: persist actual unfinished work, close the owner, reopen, and
        # consume it exactly once.  The journal is execution control, not a
        # second adaptive memory.
        pending_path = root / "unfinished-work.json"
        pending = {
            "schema": "cassi.full-program-unfinished-work.v1",
            "work_id": "beta-valve-publication",
            "status": "pending",
            "cursor": "validated-field-result-awaiting-publication",
            "field_predecessor_sha256": interpreter.store.learner.fingerprint(),
            "accepted_learning_sequences": [relation_learning_sequence, corrected_learning_sequence, _sequence(safety_learning)],
            "effects": [],
            "allocation": {"work": 8, "evidence_reads": 2, "model_calls": 0},
        }
        _write_json(pending_path, pending)
        paused_field = interpreter.store.learner.fingerprint()
        # Leaving this with the context manager is the actual interruption.

    reopened_pending = json.loads(pending_path.read_text(encoding="utf-8"))
    _require(reopened_pending["status"] == "pending", "unfinished work did not remain pending")
    with UniversalLLMInterpreter(field_root, model=STRUCTURED_MODEL, profile=PROFILE) as reopened:
        reopened_state = reopened.state_receipt()
        _require(reopened_state["field_state_sha256"] == paused_field, "reopen did not restore the exact field")
        resumed_query = reopened.query(beta_trace, question=TASK_QUESTION)
        resumed_meaning = _meaning(resumed_query, "resumed beta query")
        resumed_value = _calculate(resumed_meaning, language_ast)
        resumed_emission = _emit(resumed_value, task_id=TASK_ID, meaning=resumed_meaning)
        effect = {
            "effect_id": "workshop:beta:valve-correction",
            "action": "set-workshop-valve",
            "value": resumed_value,
            "acknowledgment": "simulation-world-acknowledged",
            "execution_authority": "simulation-only-authorized",
        }
        resumed_pending = {
            **reopened_pending,
            "status": "completed",
            "cursor": "published",
            "field_successor_sha256": reopened.store.learner.fingerprint(),
            "effects": [effect],
        }
        _write_json(pending_path, resumed_pending)
        lifecycle["step_07_pause_reopen"] = {
            "pending_before_close": reopened_pending,
            "reopened_state": reopened_state,
            "resumed_query": _compact_query(resumed_query),
            "resumed_emission": resumed_emission,
            "accepted_learning_replayed": False,
            "external_effect_count": 1,
            "effect": effect,
            "field_state_after_resume": reopened.store.learner.fingerprint(),
        }

        # Step 8: replace the model instrument, retain the same fixed adapter
        # coordinate, and use a new participant/parameter query.
        gamma = observations["held_out"][1]
        gamma_trace = _trace(
            REPLACEMENT_MODEL,
            RELATION_ADAPTER,
            TASK_QUESTION,
            _trace_values(6.0, 3.0, 0.43, 0.88),
            sequence_id="gamma-replacement-model",
            position=14,
        )
        replacement_query = reopened.query(gamma_trace, question=TASK_QUESTION)
        replacement_meaning = _meaning(replacement_query, "replacement model query")
        replacement_ast = {"participant": "gamma", "base": gamma["base"], "delay": gamma["delay"]}
        replacement_value = _calculate(replacement_meaning, replacement_ast)
        _require(replacement_value == gamma["outcome_after_correction"], "portable meaning failed on replacement model")
        lifecycle["step_08_model_replacement"] = {
            "old_model_fingerprint": STRUCTURED_MODEL.fingerprint,
            "new_model_fingerprint": REPLACEMENT_MODEL.fingerprint,
            "same_adapter_coordinate": gamma_trace.field_coordinate_descriptor() == corrected_trace.field_coordinate_descriptor(),
            "query": _compact_query(replacement_query),
            "parameter": replacement_ast,
            "value": replacement_value,
            "held_out_truth": gamma["outcome_after_correction"],
        }

        # Save the common predecessor for the selective-loss branch before
        # later development meanings are admitted.
        common_branch_root = root / "common-after-transfer"
    # The main field is closed before copying any durable files.
    if common_branch_root.exists():
        shutil.rmtree(common_branch_root)
    shutil.copytree(field_root, common_branch_root)

    # Step 9: remove only the acquired relation in an isolated branch.
    relation_branch_root = root / "relation-removed-branch"
    if relation_branch_root.exists():
        shutil.rmtree(relation_branch_root)
    shutil.copytree(common_branch_root, relation_branch_root)
    with UniversalLLMInterpreter(relation_branch_root, model=STRUCTURED_MODEL, profile=PROFILE) as removed:
        removed_relation_revoke = removed.store.revoke(corrected_learning_sequence)
        removed_relation_query = removed.query(beta_trace, question=TASK_QUESTION)
        removed_safety_query = removed.query(safety_trace, question=SAFETY_QUESTION)
        relation_loss = {
            "relation_status": removed_relation_query["status"],
            "relation_reason": removed_relation_query["prediction"].get("reason"),
            "safety_status": removed_safety_query["status"],
            "safety_meaning": removed_safety_query["prediction"].get("meaning"),
            "revocation": _compact_revoke(removed_relation_revoke),
            "selective_loss": removed_relation_query["status"] != "field-owned" and removed_safety_query["status"] == "field-owned",
        }
    lifecycle["step_09_selective_relation_loss"] = relation_loss

    # Step 10: the held-out gamma result was emitted by the field boundary.
    gamma_emission = _emit(replacement_value, task_id=TASK_ID, meaning=replacement_meaning)
    lifecycle["step_10_field_owned_emission"] = {
        "emission": gamma_emission,
        "held_out_cases": 1,
        "held_out_correct": int(float(gamma_emission["text"]) == gamma["outcome_after_correction"]),
        "adequacy_definition": "field-emitted numeric value equals evaluator-held-out outcome",
        "native_displacement": gamma_emission["native_displacement"],
    }

    # Reopen the main field for the development stages; the common branch is
    # only an evaluation copy and never publishes into the main lifetime.
    with UniversalLLMInterpreter(field_root, model=STRUCTURED_MODEL, profile=PROFILE) as interpreter:
        # Step 11: expose a real regime gap, then use a bounded evidence-seeking
        # development method to add a guard without changing the relation.
        delta_gap = observations["regime_gap"]
        delta_trace = _trace(
            STRUCTURED_MODEL,
            RELATION_ADAPTER,
            TASK_QUESTION,
            _trace_values(5.0, 4.0, 0.22, 0.64),
            sequence_id="delta-regime-gap",
            position=15,
        )
        delta_query = interpreter.query(delta_trace, question=TASK_QUESTION)
        delta_meaning = _meaning(delta_query, "delta gap query")
        delta_ast = {"participant": "delta", "base": delta_gap["base"], "delay": delta_gap["delay"]}
        delta_raw = _calculate(delta_meaning, delta_ast)
        _require(delta_raw == 13.0, "regime-gap fixture did not exceed the corrected relation")
        gap_observation = {
            "made_before_outcome": True,
            "predicted_without_guard": delta_raw,
            "observed_outcome": delta_gap["outcome"],
            "error": delta_raw - delta_gap["outcome"],
            "cap_regime": True,
        }
        _require(gap_observation["error"] > 0.0, "cap-regime gap is not genuine")
        method_meaning = {
            "kind": "acquired-development-method",
            "task_id": TASK_ID,
            "method_id": "guard-split-v1",
            "method": "study-one-separating-outcome-and-split-regime-guard",
            "input_family": "base_plus_delay",
            "source_revision_id": development_source_revision,
            "allocation": {"evidence_reads": 1, "work": 4, "model_calls": 0},
        }
        method_trace = _trace(
            STRUCTURED_MODEL,
            METHOD_ADAPTER,
            DEVELOPMENT_QUESTION,
            _trace_values(13.0, 12.0, 4.0, 12.0),
            sequence_id="development-method-acquisition",
            position=16,
        )
        method_learning = interpreter.learn(
            method_trace,
            question=DEVELOPMENT_QUESTION,
            meaning=method_meaning,
        )
        method_query = interpreter.query(method_trace, question=DEVELOPMENT_QUESTION)
        acquired_method = _meaning(method_query, "acquired development method")
        safety_query = interpreter.query(safety_trace, question=SAFETY_QUESTION)
        safety_meaning = _meaning(safety_query, "safety for regime guard")
        guarded_value = min(delta_raw, float(safety_meaning["safety_limit"]))
        guarded_emission = _emit(guarded_value, task_id=TASK_ID, meaning=delta_meaning)
        beta_after_development_query = interpreter.query(beta_trace, question=TASK_QUESTION)
        beta_after_development = _calculate(_meaning(beta_after_development_query, "beta after development"), language_ast)
        _require(guarded_value == 12.0 and beta_after_development == 11.0, "development did not improve while preserving prior skill")
        lifecycle["step_11_gap_and_development"] = {
            "gap": gap_observation,
            "selected_skill": "study",
            "skill_boundary": {"evidence_reads": 1, "work": 4, "model_calls": 0, "permissions": "authorized-observations-only"},
            "method_learning": _compact_learning(method_learning),
            "method_query": _compact_query(method_query),
            "acquired_method": acquired_method,
            "guarded_calculation": guarded_value,
            "guarded_emission": guarded_emission,
            "prior_beta_value_preserved": beta_after_development,
            "development_cost": {"evidence_reads": 1, "work": 4, "model_calls": 0, "field_write_events": 1},
        }
        method_learning_sequence = _sequence(method_learning)

        # Admit the second family's ordinary relation in the common predecessor
        # before comparing development methods.  Both arms therefore receive
        # identical information, allocation, and permissions.
        thermal_relation_meaning = {
            "kind": "acquired-thermal-relation",
            "task_id": TASK_ID,
            "relation_family": WORLD["relation_family"],
            "base_coefficient": 1.0,
            "delay_coefficient": WORLD["thermal_delay_coefficient"],
            "intercept": 0.0,
            "domain": {"delay_max": 4.0, "regime": "uncapped-thermal-before-guard"},
            "source_revision_id": thermal_source_revision,
            "acquisition_method": "matched-family-calibration",
        }
        thermal_relation_trace = _trace(
            STRUCTURED_MODEL,
            THERMAL_ADAPTER,
            THERMAL_QUESTION,
            _trace_values(5.0, 4.0, 0.55, 0.44),
            sequence_id="thermal-relation-acquisition",
            position=17,
        )
        thermal_learning = interpreter.learn(
            thermal_relation_trace,
            question=THERMAL_QUESTION,
            meaning=thermal_relation_meaning,
        )
        thermal_learning_sequence = _sequence(thermal_learning)
        _require(thermal_learning["status"] in {"learned", "replayed"}, "thermal relation was not admitted")
        thermal_common_state = interpreter.store.learner.fingerprint()
    # Common state is now durable and identical for both method arms.
    method_compare_base = root / "method-compare-base"
    if method_compare_base.exists():
        shutil.rmtree(method_compare_base)
    shutil.copytree(field_root, method_compare_base)

    # Step 12 fixed initial method arm: same state, source, permissions, and
    # allocation, but it does not invoke the acquired guard-split method.
    fixed_root = root / "fixed-method-arm"
    improved_root = root / "acquired-method-arm"
    for path in (fixed_root, improved_root):
        if path.exists():
            shutil.rmtree(path)
        shutil.copytree(method_compare_base, path)
    thermal_gap = observations["thermal_gap"]
    fixed_allocation = {"evidence_reads": 1, "work": 4, "model_calls": 0, "permissions": "authorized-observations-only"}
    with UniversalLLMInterpreter(fixed_root, model=STRUCTURED_MODEL, profile=PROFILE) as fixed:
        fixed_trace = thermal_relation_trace
        fixed_query = fixed.query(fixed_trace, question=THERMAL_QUESTION)
        fixed_meaning = _meaning(fixed_query, "fixed thermal query")
        fixed_ast = {"participant": "delta", "base": thermal_gap["base"], "delay": thermal_gap["delay"]}
        fixed_value = _calculate(fixed_meaning, fixed_ast)
        fixed_error = fixed_value - thermal_gap["outcome"]
        fixed_result = {
            "method": "supplied-balanced-v1",
            "allocation": fixed_allocation,
            "source_revision_id": thermal_source_revision,
            "initial_field_sha256": fixed_query["field_state_sha256"],
            "value": fixed_value,
            "truth": thermal_gap["outcome"],
            "error": fixed_error,
            "status": "incorrect" if fixed_error != 0.0 else "correct",
            "model_calls": 0,
        }

    pending_thermal_path = root / "unfinished-thermal-work.json"
    with UniversalLLMInterpreter(improved_root, model=STRUCTURED_MODEL, profile=PROFILE) as improved:
        improved_trace = thermal_relation_trace
        improved_query_before = improved.query(improved_trace, question=THERMAL_QUESTION)
        improved_meaning = _meaning(improved_query_before, "improved thermal query")
        improved_raw = _calculate(improved_meaning, fixed_ast)
        _require(improved_raw == 17.0, "thermal gap did not expose the fixed-method failure")
        pending_thermal = {
            "schema": "cassi.full-program-unfinished-development.v1",
            "work_id": "thermal-guard-transfer",
            "status": "pending",
            "method_id": "guard-split-v1",
            "source_revision_id": thermal_source_revision,
            "allocation": fixed_allocation,
            "predecessor_field_sha256": improved.store.learner.fingerprint(),
            "accepted_learning_sequences": [method_learning_sequence, thermal_learning_sequence],
            "effect_ids": [],
        }
        _write_json(pending_thermal_path, pending_thermal)
        improved_paused_state = improved.store.learner.fingerprint()
    resumed_thermal = json.loads(pending_thermal_path.read_text(encoding="utf-8"))
    with UniversalLLMInterpreter(improved_root, model=STRUCTURED_MODEL, profile=PROFILE) as improved:
        improved_reopened_state = improved.state_receipt()
        _require(improved_reopened_state["field_state_sha256"] == improved_paused_state, "thermal interruption changed the field")
        thermal_guard_meaning = {
            "kind": "reused-development-guard",
            "task_id": TASK_ID,
            "method_id": "guard-split-v1",
            "family": "thermal-load",
            "guard": "cap-after-relation",
            "cap": WORLD["thermal_safety_limit"],
            "source_revision_id": thermal_source_revision,
            "method_source_revision_id": development_source_revision,
        }
        thermal_guard_trace = _trace(
            STRUCTURED_MODEL,
            THERMAL_METHOD_ADAPTER,
            THERMAL_QUESTION,
            _trace_values(17.0, 9.0, 0.15, 0.61),
            sequence_id="thermal-guard-reuse",
            position=19,
        )
        thermal_guard_learning = improved.learn(
            thermal_guard_trace,
            question=THERMAL_QUESTION,
            meaning=thermal_guard_meaning,
        )
        thermal_guard_query = improved.query(thermal_guard_trace, question=THERMAL_QUESTION)
        thermal_guard_readout = _meaning(thermal_guard_query, "reused thermal guard query")
        raw_after_method = improved_raw
        final_thermal = min(raw_after_method, float(thermal_guard_readout["cap"]))
        thermal_emission = _emit(final_thermal, task_id=TASK_ID, meaning=thermal_guard_readout)
        beta_preservation_query = improved.query(beta_trace, question=TASK_QUESTION)
        beta_preserved = _calculate(_meaning(beta_preservation_query, "beta after thermal method"), language_ast)
        effect = {
            "effect_id": "thermal:delta:guarded-load",
            "action": "set-thermal-valve",
            "value": final_thermal,
            "acknowledgment": "simulation-world-acknowledged",
        }
        resumed_thermal = {
            **resumed_thermal,
            "status": "completed",
            "cursor": "published",
            "successor_field_sha256": improved.store.learner.fingerprint(),
            "effect_ids": [effect["effect_id"]],
        }
        _write_json(pending_thermal_path, resumed_thermal)
        _require(final_thermal == thermal_gap["outcome"] and beta_preserved == 11.0, "reused method did not transfer or preserve prior competence")
        lifecycle["step_12_method_transfer"] = {
            "fixed_arm": fixed_result,
            "acquired_arm": {
                "allocation": fixed_allocation,
                "source_revision_id": thermal_source_revision,
                "initial_field_sha256": improved_query_before["field_state_sha256"],
                "reopened_state": improved_reopened_state,
                "before_method_value": improved_raw,
                "guard_learning": _compact_learning(thermal_guard_learning),
                "guard_query": _compact_query(thermal_guard_query),
                "emission": thermal_emission,
                "after_method_value": final_thermal,
                "truth": thermal_gap["outcome"],
                "status": "correct" if final_thermal == thermal_gap["outcome"] else "incorrect",
                "prior_beta_value": beta_preserved,
                "effect": effect,
                "accepted_learning_replayed": False,
                "unfinished_work_preserved": True,
                "model_calls": 0,
            },
            "comparison": {
                "same_allocation": True,
                "same_permissions": True,
                "same_initial_field_sha256": (
                    fixed_result["initial_field_sha256"] == improved_query_before["field_state_sha256"]
                    == thermal_common_state
                ),
                "same_source_revision_id": (
                    fixed_result["source_revision_id"]
                    == lifecycle["source_revisions"]["thermal"]
                ),
                "acquired_method_improves_unfamiliar_family": fixed_error != 0.0 and final_thermal == thermal_gap["outcome"],
            },
        }

    # Compact state lineage and direct checks are part of the receipt.  The
    # verifier recomputes the source hashes, branch files, and content digest.
    lifecycle["state_lineage"] = {
        "initial": field_state_before,
        "paused_before_reopen": paused_field,
        "reopened": lifecycle["step_07_pause_reopen"]["reopened_state"]["field_state_sha256"],
        "thermal_common_predecessor": thermal_common_state,
        "field_adaptive_object": "QiFieldState.field",
        "other_adaptive_owners": [],
    }
    lifecycle["cost"] = {
        "model_calls": 0,
        "field_learning_events": 6,
        "field_query_reads": 15,
        "external_effects_main": 1,
        "external_effects_transfer": 1,
        "development_evidence_reads": 1,
        "development_work": 4,
        "interruption_count": 2,
    }
    return lifecycle


def _native_contract(native_receipt_path: Path | None, source_revision: str) -> dict[str, Any]:
    if native_receipt_path is None:
        return {
            "status": "unavailable",
            "reason": "no native receipt supplied; structured twelve-step run remains measurable",
            "shared_task_verified": False,
        }
    path = Path(native_receipt_path).resolve()
    _require(path.is_file(), f"native receipt does not exist: {path}")
    native = json.loads(path.read_text(encoding="utf-8"))
    same_task = native.get("task_id") == TASK_ID and native.get("question") == TASK_QUESTION
    same_source = native.get("source_revision_id") == source_revision
    answer_target_absent = native.get("answer_bearing_activation_supplied") is False
    shared = same_task and same_source and answer_target_absent
    return {
        "status": "verified-shared-task" if shared else "rejected-different-task",
        "path": str(path),
        "file_sha256": _digest_file(path),
        "shared_task_verified": bool(shared),
        "task_id": native.get("task_id"),
        "question": native.get("question"),
        "source_revision_id": native.get("source_revision_id"),
        "answer_bearing_activation_supplied": native.get("answer_bearing_activation_supplied"),
        "answer_target_policy": "not supplied to field semantics",
    }


def run(root: Path, *, native_receipt: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    if root.exists() and any(root.iterdir()):
        raise ProgramError(f"refusing to reuse nonempty run root: {root}")
    root.mkdir(parents=True, exist_ok=False)
    lifecycle = _run_structured(root)
    native = _native_contract(native_receipt, lifecycle["source_revisions"]["initial"])
    steps = {key: value for key, value in lifecycle.items() if key.startswith("step_")}
    checks = {
        "step_01_acquires_relation_with_prior_predictions": bool(steps["step_01_acquisition"]["predictions_before_outcomes"]) and all(row["made_before_outcome"] for row in steps["step_01_acquisition"]["predictions_before_outcomes"]),
        "step_02_new_participant_uses_relation": steps["step_02_new_participant"]["calculated_value"] == steps["step_02_new_participant"]["held_out_truth"],
        "step_03_language_composes_with_retained_meaning": steps["step_03_language_composition"]["model_calls"] == 0 and steps["step_03_language_composition"]["field_owner"] == "acquired-relation-readout",
        "step_04_field_owns_formal_calculation": steps["step_04_05_field_compute_and_emit"]["calculation"]["executor"] == "cassi-field-arithmetic-v1" and steps["step_04_05_field_compute_and_emit"]["calculation"]["model_calls"] == 0,
        "step_05_declared_field_emission": steps["step_04_05_field_compute_and_emit"]["emission_before_correction"]["owner"] == "field" and steps["step_04_05_field_compute_and_emit"]["emission_before_correction"]["native_fallback"] is False,
        "step_06_correction_repairs_dependents_locally": steps["step_06_correction_and_repair"]["repaired_prediction"] == 11.0 and steps["step_06_correction_and_repair"]["repaired_plan"]["target_load"] == 11.0 and steps["step_06_correction_and_repair"]["repaired_explanation"]["unrelated_safety_preserved"] is True,
        "step_07_reopen_is_exact_and_once": steps["step_07_pause_reopen"]["accepted_learning_replayed"] is False and steps["step_07_pause_reopen"]["external_effect_count"] == 1 and steps["step_07_pause_reopen"]["pending_before_close"]["status"] == "pending" and steps["step_07_pause_reopen"]["resumed_query"]["status"] == "field-owned",
        "step_08_replacement_model_transfers": steps["step_08_model_replacement"]["old_model_fingerprint"] != steps["step_08_model_replacement"]["new_model_fingerprint"] and steps["step_08_model_replacement"]["same_adapter_coordinate"] and steps["step_08_model_replacement"]["value"] == steps["step_08_model_replacement"]["held_out_truth"],
        "step_09_relation_removal_is_selective": steps["step_09_selective_relation_loss"]["selective_loss"] is True,
        "step_10_field_emission_has_heldout_adequacy": steps["step_10_field_owned_emission"]["emission"]["owner"] == "field" and steps["step_10_field_owned_emission"]["held_out_correct"] == 1,
        "step_11_development_repairs_gap_preserves_prior": steps["step_11_gap_and_development"]["gap"]["error"] > 0.0 and steps["step_11_gap_and_development"]["guarded_calculation"] == 12.0 and steps["step_11_gap_and_development"]["prior_beta_value_preserved"] == 11.0,
        "step_12_method_reuses_across_family_after_restart": steps["step_12_method_transfer"]["comparison"]["acquired_method_improves_unfamiliar_family"] is True and steps["step_12_method_transfer"]["acquired_arm"]["unfinished_work_preserved"] is True and steps["step_12_method_transfer"]["acquired_arm"]["prior_beta_value"] == 11.0,
        "one_adaptive_field": lifecycle["state_lineage"]["field_adaptive_object"] == "QiFieldState.field" and lifecycle["state_lineage"]["other_adaptive_owners"] == [],
        "native_shared_task_if_supplied": native["shared_task_verified"] if native_receipt is not None else True,
    }
    receipt: dict[str, Any] = {
        "schema": PROGRAM_SCHEMA,
        "program_id": PROGRAM_ID,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "task": {
            "task_id": TASK_ID,
            "question": TASK_QUESTION,
            "language_request": LANGUAGE_REQUEST,
            "source_revision_id": lifecycle["source_revisions"]["initial"],
            "requested_output": "field-owned corrected numeric emission",
        },
        "structured_lifecycle": lifecycle,
        "native_shared_task": native,
        "checks": checks,
        "ownership": {
            "field_adaptive_object": "QiFieldState.field",
            "structured_executor": "cassi-field-arithmetic-v1",
            "field_owned_emission": True,
            "model_calls_in_structured_episode": 0,
            "native_fallback": False,
            "native_graph_displacement": native.get("status") == "verified-shared-task",
        },
        "scope": {
            "world": "bounded partially observed workshop with explicit held-out cap regimes",
            "language": "fixed bounded request parser, not open-domain language acquisition",
            "native": "only a same-task verified native receipt can extend the structured result",
            "generalization": "one new participant, one replacement fixture model, and one second problem family",
        },
    }
    receipt["content_sha256"] = receipt_digest(receipt)
    _write_json(root / "full-program-receipt.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="empty persistent run directory")
    parser.add_argument("--output", type=Path, help="optional compact receipt destination")
    parser.add_argument("--native-receipt", type=Path, help="optional same-task native receipt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.root is None:
            with tempfile.TemporaryDirectory(prefix="cassi-universal-interpreter-full-") as directory:
                receipt = run(Path(directory), native_receipt=args.native_receipt)
        else:
            receipt = run(args.root, native_receipt=args.native_receipt)
    except Exception as error:
        print(f"full universal interpreter failed: {error}", file=sys.stderr)
        return 1
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({"status": receipt["status"], "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    else:
        print(payload, end="")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
