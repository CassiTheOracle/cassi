#!/usr/bin/env python3
"""Run the continuing-world universal-interpreter R&D program.

The program composes the exercised CassiFI packet-aware reasoning world with
one model-agnostic field-owned interpreter boundary.  A single task is admitted
through the resident work loop, corrected and reopened, bound to an archived
source, and then handed to the interpreter.  The interpreter learns one
portable meaning through a fixed adapter coordinate, answers an unfamiliar
trace from a second model identity, and survives an exact restart.

This is a composition and provenance run, not a claim that a fixture model is
an open-domain language system.  Native Qwen graph evidence remains linked to
its dedicated native program because this runner deliberately does not rerun a
GPU graph as part of the bounded continuing-world episode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent / "CassiFI"))

from cassi_raw_event_field import AcquisitionProfile  # noqa: E402
from cassi_universal_interpreter import (  # noqa: E402
    ActivationTrace,
    ModelIdentity,
    UniversalLLMInterpreter,
    receipt_digest,
)
from run_cassi_reasoning_scenario import (  # noqa: E402
    stage_five,
    stage_four,
    stage_one,
    stage_seven,
    stage_six,
    stage_three,
    stage_two,
    stages,
    task_state,
    transcript,
    world,
)
from cassi_hive_session import open_field_session  # noqa: E402


PROGRAM_SCHEMA = "cassi.universal-interpreter-program.v1"
HANDOFF_SCHEMA = "cassi.universal-interpreter-task-handoff.v1"
PROGRAM_ID = "universal-interpreter-workshop-20260917"
TASK_ID = "universal-interpreter-workshop"
TASK_QUESTION = "Determine the corrected workshop load and emit its correction."
ADAPTER_KEY = "arithmetic/correction/quotient-v1"

FIXTURE_MODEL = ModelIdentity(
    model_id="universal-interpreter-fixture",
    model_sha256="11" * 32,
    architecture="fixture-hybrid-observatory",
    quantization="fixture-f32",
    tokenizer_sha256="22" * 32,
    runtime_id="fixture-runtime",
    runtime_sha256="33" * 32,
    context_tokens=128,
    embedding_width=16,
    layer_count=8,
    backend="offline-fixture",
    hook_sites=("layer_input",),
)

ALTERNATE_MODEL = ModelIdentity(
    model_id="universal-interpreter-alternate-fixture",
    model_sha256="44" * 32,
    architecture="alternate-hybrid-observatory",
    quantization="alternate-f32",
    tokenizer_sha256="55" * 32,
    runtime_id="alternate-runtime",
    runtime_sha256="66" * 32,
    context_tokens=128,
    embedding_width=16,
    layer_count=8,
    backend="offline-fixture",
    hook_sites=("layer_input",),
)


def _prompt_digest() -> str:
    return hashlib.sha256(TASK_QUESTION.encode("utf-8")).hexdigest()


def _trace(
    model: ModelIdentity,
    values: np.ndarray,
    *,
    sequence_id: str,
    position: int,
) -> ActivationTrace:
    logits = np.full(64, -2.0, dtype=np.float32)
    logits[5] = 0.5
    logits[42] = 1.0
    return ActivationTrace(
        model=model,
        site="layer_input",
        layer=5,
        sequence_id=sequence_id,
        position=position,
        values=np.asarray(values, dtype=np.float32),
        token_id=17,
        expected_token_id=42,
        logits=logits,
        adapter_key=ADAPTER_KEY,
        prompt_sha256=_prompt_digest(),
        source_id=f"{TASK_ID}:{sequence_id}",
    )


def _profile() -> AcquisitionProfile:
    return AcquisitionProfile(
        wave_width=512,
        payload_limit=16,
        trace_horizon=2,
        minimum_score=0.58,
        minimum_margin=0.08,
    )


def _json_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    """Reject non-receipt values instead of stringifying evidence."""

    return json.loads(
        json.dumps(
            dict(value),
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _f32_digest(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(values, dtype="<f4").tobytes(order="C")
    ).hexdigest()


def _packet_trace_values(task: Mapping[str, Any]) -> np.ndarray:
    """Select a nonzero successor row from the retained packet continuation."""

    def visit(value: Any) -> np.ndarray | None:
        if isinstance(value, Mapping):
            wave_words = value.get("wave_words")
            if isinstance(wave_words, Mapping):
                raw = wave_words.get("values")
                if isinstance(raw, list):
                    candidate = np.asarray(raw, dtype=np.float32)
                    if candidate.ndim == 1 and candidate.size >= 16:
                        if bool(np.isfinite(candidate).all()):
                            nonzero = np.flatnonzero(
                                np.abs(candidate) > 1.0e-12
                            )
                            if nonzero.size:
                                start = min(
                                    int(nonzero[0]),
                                    int(candidate.size) - 16,
                                )
                                return candidate[start : start + 16].copy()
            for key in sorted(value, key=str):
                found = visit(value[key])
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = visit(item)
                if found is not None:
                    return found
        return None

    selected = visit(task)
    if selected is None:
        raise RuntimeError("packet continuation has no nonzero trace row")
    return selected


def _run_packet_world(root: Path) -> dict[str, Any]:
    """Exercise the existing packet program on a private continuing world."""

    packet_root = root / "packet-world"
    if packet_root.exists():
        shutil.rmtree(packet_root)
    packet_root.mkdir(parents=True)

    # The scenario module keeps its compact stage map at module scope.  Reset
    # it so this runner is replay-safe when called more than once in a process.
    stages.clear()
    transcript.clear()
    scene = world()
    with open_field_session(
        packet_root,
        role="worker",
        mode="scout",
        hive_home=root / "hive",
        hive_id="main",
        metadata={"program": PROGRAM_ID, "arm": "packet-world"},
    ) as owner:
        stage_one(owner, scene)
        stage_two(owner, scene)
        stage_three(owner, scene)
        stage_four(owner, scene)
        stage_five(scene)
        stage_six(owner)
        stage_seven(owner)
        final_task_raw = task_state(owner)
        trace_values = _packet_trace_values(final_task_raw)
        final_task = _json_copy(final_task_raw)
    packet = {
        "schema": "cassi.universal-interpreter-packet-world.v1",
        "program_id": PROGRAM_ID,
        "episode_id": "workshop-episode",
        "stages": _json_copy(stages),
        "transcript": list(transcript),
        "final_task_state": final_task,
        "packet_trace": {
            "source": "final_task_state.wave_words",
            "values": trace_values.tolist(),
            "values_sha256": _f32_digest(trace_values),
        },
    }
    return packet


def _run_native_boundary(root: Path, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Run the fixed interpreter boundary after the packet correction."""

    native_root = root / "field-interpreter"
    if native_root.exists():
        shutil.rmtree(native_root)
    native_root.mkdir(parents=True)

    packet_trace = packet["packet_trace"]
    trace_values = np.asarray(packet_trace["values"], dtype=np.float32)
    if trace_values.ndim != 1 or trace_values.size != 16:
        raise RuntimeError("packet world did not export the bounded trace row")
    if not bool(np.isfinite(trace_values).all()) or not bool(
        np.any(np.abs(trace_values) > 1.0e-12)
    ):
        raise RuntimeError("packet world exported an empty trace row")
    training_values = trace_values[:8].copy()
    held_out_values = trace_values[8:16].copy()
    training = _trace(
        FIXTURE_MODEL,
        training_values,
        sequence_id="training-correction",
        position=10,
    )
    held_out = _trace(
        FIXTURE_MODEL,
        held_out_values,
        sequence_id="held-out-correction",
        position=11,
    )
    alternate = _trace(
        ALTERNATE_MODEL,
        held_out_values,
        sequence_id="alternate-model-correction",
        position=11,
    )
    corrected_load = float(packet["stages"]["s3_correction_and_reopen"]["premise_after"])
    source_revision_id = str(packet["stages"]["s7_source_binding"]["source_revision_id"])
    meaning = {
        "kind": "model-correction",
        "task_id": TASK_ID,
        "corrected_load": corrected_load,
        "next_token_id": 42,
        "text": "42",
        "rule": "the field-owned answer carries the corrected workshop premise",
        "source_revision_id": source_revision_id,
    }

    with UniversalLLMInterpreter(
        native_root,
        model=FIXTURE_MODEL,
        profile=_profile(),
    ) as interpreter:
        initial_state = interpreter.state_receipt()
        inspection = interpreter.inspect(training)
        state_before_learning = interpreter.state_receipt()
        learning = interpreter.learn(
            training,
            question=TASK_QUESTION,
            meaning=meaning,
        )
        state_after_learning = interpreter.state_receipt()
        query = interpreter.query(held_out, question=TASK_QUESTION)
        alternate_query = interpreter.query(alternate, question=TASK_QUESTION)
        explanation = interpreter.explain(held_out, question=TASK_QUESTION)
        ownership = interpreter.ownership_receipt()
        field_state_before_close = interpreter.store.learner.fingerprint()

    with UniversalLLMInterpreter(
        native_root,
        model=FIXTURE_MODEL,
        profile=_profile(),
    ) as restarted:
        restarted_state = restarted.state_receipt()
        restart_query = restarted.query(held_out, question=TASK_QUESTION)
        field_state_after_restart_query = restarted.store.learner.fingerprint()

    checks = {
        "inspection_non_mutating": state_before_learning["field_state_sha256"]
        == inspection["field_state_sha256"]
        == initial_state["field_state_sha256"],
        "trace_values_are_packet_derived": _f32_digest(trace_values)
        == packet_trace["values_sha256"]
        and training.as_dict()["values_sha256"] == _f32_digest(training_values)
        and held_out.as_dict()["values_sha256"] == _f32_digest(held_out_values),
        "held_out_trace_is_distinct": not np.array_equal(
            training_values, held_out_values
        ),
        "field_prediction_supported": query["status"] == "field-owned",
        "field_prediction_matches_target": query["prediction"]["target_token_match"] is True,
        "alternate_model_reuses_fixed_coordinate": alternate_query["status"] == "field-owned"
        and alternate_query["prediction"]["meaning"] == meaning
        and alternate_query["prediction"]["target_token_match"] is True
        and alternate.model.fingerprint != training.model.fingerprint,
        "restart_preserves_field": field_state_before_close
        == restarted_state["field_state_sha256"]
        == field_state_after_restart_query,
        "restart_replays_meaning": restart_query["prediction"]["meaning"] == meaning,
        "no_native_fallback": query["native_fallback"] is False
        and alternate_query["native_fallback"] is False
        and restart_query["native_fallback"] is False,
        "one_adaptive_field": ownership["field_adaptive_object"] == "QiFieldState.field"
        and ownership["fallback"] == "none",
    }
    return {
        "schema": "cassi.universal-interpreter-boundary.v1",
        "task_id": TASK_ID,
        "question": TASK_QUESTION,
        "model": FIXTURE_MODEL.as_dict(),
        "alternate_model": ALTERNATE_MODEL.as_dict(),
        "adapter_key": ADAPTER_KEY,
        "packet_trace_sha256": packet_trace["values_sha256"],
        "training_values_sha256": _f32_digest(training_values),
        "held_out_values_sha256": _f32_digest(held_out_values),
        "training_trace": training.as_dict(),
        "held_out_trace": held_out.as_dict(),
        "alternate_trace": alternate.as_dict(),
        "initial_state": initial_state,
        "inspection": inspection,
        "learning": learning,
        "state_before_learning": state_before_learning,
        "state_after_learning": state_after_learning,
        "query": query,
        "alternate_query": alternate_query,
        "explanation": explanation,
        "restart_query": restart_query,
        "restarted_state": restarted_state,
        "ownership": ownership,
        "checks": checks,
    }


def run(root: Path) -> dict[str, Any]:
    """Run both surfaces and return one content-addressed program receipt."""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    packet = _run_packet_world(root)
    native = _run_native_boundary(root, packet)
    packet_stages = packet["stages"]
    packet_question = packet_stages["s2_open_episode"]["question"]
    handoff = {
        "schema": HANDOFF_SCHEMA,
        "program_id": PROGRAM_ID,
        "task_id": TASK_ID,
        "episode_id": packet["episode_id"],
        "question": TASK_QUESTION,
        "packet_question": packet_question,
        "source_revision_id": packet_stages["s7_source_binding"]["source_revision_id"],
        "premise_before": packet_stages["s1_world"]["premise"],
        "premise_after": packet_stages["s3_correction_and_reopen"]["premise_after"],
        "native_model_fingerprint": native["training_trace"]["model_fingerprint"],
        "native_adapter_key": native["adapter_key"],
        "native_trace_sha256": native["training_trace"]["trace_sha256"],
        "packet_trace_sha256": packet["packet_trace"]["values_sha256"],
        "native_packet_trace_sha256": native["packet_trace_sha256"],
        "meaning_source_revision_id": native["learning"]["ledger"]["source_revision_id"]
        if "source_revision_id" in native["learning"]["ledger"]
        else native["query"]["prediction"]["meaning"]["source_revision_id"],
    }
    checks = {
        "packet_resident_episode_reopened": packet_stages["s3_correction_and_reopen"]["phase"]
        == "terminal"
        and packet_stages["s3_correction_and_reopen"]["transports_after_reopen"] >= 1,
        "packet_correction_applied": packet_stages["s1_world"]["premise"] == 2.0
        and packet_stages["s3_correction_and_reopen"]["premise_after"] == 5.0
        and bool(packet_stages["s3_correction_and_reopen"]["repairs"]),
        "packet_selection_frontier_exercised": set(packet_stages["s4_selection_methods"]["scheduler_methods"]) 
        == {"baseline", "hierarchy", "static", "live", "shuffled", "acquired"},
        "packet_refinement_exercised": packet_stages["s6_refinement"]["refinement_status"]
        == "refined"
        and packet_stages["s6_refinement"]["item_kinds"].get("refine", 0) == 1,
        "packet_source_binding_enforced": bool(packet_stages["s7_source_binding"]["bound_row"])
        and set(packet_stages["s7_source_binding"]["refusals"]) 
        == {"unadmitted_source", "span_outside_source", "unknown_revision"},
        "semantic_question_handoff": packet_question["task_id"] == TASK_ID
        and packet_question["prompt"] == TASK_QUESTION
        and handoff["question"] == packet_question["prompt"],
        "corrected_meaning_handoff": handoff["premise_after"]
        == native["query"]["prediction"]["meaning"]["corrected_load"]
        == 5.0,
        "source_handoff_preserved": handoff["source_revision_id"]
        == native["query"]["prediction"]["meaning"]["source_revision_id"]
        == handoff["meaning_source_revision_id"],
        "packet_to_native_trace_handoff": handoff["packet_trace_sha256"]
        == handoff["native_packet_trace_sha256"]
        == native["packet_trace_sha256"],
        "native_boundary_passed": all(native["checks"].values()),
        "cross_model_portability_passed": native["checks"]["alternate_model_reuses_fixed_coordinate"],
    }
    receipt: dict[str, Any] = {
        "schema": PROGRAM_SCHEMA,
        "program_id": PROGRAM_ID,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "task": {
            "task_id": TASK_ID,
            "question": TASK_QUESTION,
            "requested_output": "field-owned correction",
            "semantic_boundary": "packet correction and fixed model translation",
        },
        "program_dimensions": {
            "continuing_world": "CassiFI resident packet episode with correction, reopen, refinement, and source binding",
            "model_boundary": "fixed adapter coordinate with two model identities",
            "adaptive_state": "two explicit owners: packet regional workspace and interpreter QiFieldState.field",
            "interpreter_adaptive_state": "one UniversalLLMInterpreter QiFieldState.field",
            "integration_boundary": "task, source, and bounded trace metadata only; no shared adaptive tensor or hidden projection",
            "evidence": "packet source revision and immutable activation traces",
            "emission": "field-owned meaning delivery; no native fallback",
            "native_graph": "not rerun in this composition receipt; see dedicated native program",
        },
        "packet_world": packet,
        "task_handoff": handoff,
        "native_boundary": native,
        "checks": checks,
    }
    receipt["content_sha256"] = receipt_digest(receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        help="persistent program directory; defaults to a temporary run directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional receipt JSON path; otherwise print the receipt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.root is not None:
        receipt = run(args.root)
    else:
        with tempfile.TemporaryDirectory(prefix="cassi-universal-interpreter-program-") as directory:
            receipt = run(Path(directory))
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
