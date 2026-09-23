#!/usr/bin/env python3
"""Run a complete field-owned universal-interpreter possession transfer.

The default run is a deterministic fixture that exercises the same contracts
used by real hidden-state and GGUF adapters: immutable activation reading,
fixed model-to-field coordinates, correction admission, field-only prediction,
exact restart, a bounded weight observation, and honest causal classification.
Use ``--root`` to retain the generated field checkpoint and journal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from cassi_raw_event_field import AcquisitionProfile
from cassi_universal_interpreter import (
    ActivationTrace,
    CausalPair,
    ModelIdentity,
    OutputSnapshot,
    UniversalLLMInterpreter,
    WeightSlice,
    receipt_digest,
)


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


def _prompt_digest() -> str:
    return hashlib.sha256(b"universal-interpreter-demo-prompt").hexdigest()


def _trace(
    values: list[float],
    *,
    sequence_id: str,
    position: int,
) -> ActivationTrace:
    logits = np.full(64, -2.0, dtype=np.float32)
    logits[5] = 0.5
    logits[42] = 1.0
    return ActivationTrace(
        model=FIXTURE_MODEL,
        site="layer_input",
        layer=5,
        sequence_id=sequence_id,
        position=position,
        values=np.asarray(values, dtype=np.float32),
        token_id=17,
        expected_token_id=42,
        logits=logits,
        # This is a fixed adapter coordinate, not a learned representation.
        adapter_key="arithmetic/correction/quotient-v1",
        prompt_sha256=_prompt_digest(),
        source_id=f"fixture:{sequence_id}",
    )


def _causal_fixture() -> dict[str, Any]:
    baseline_logits = np.asarray([0.0, 2.0, 1.0, -1.0], dtype=np.float32)
    lesion_logits = np.asarray([0.0, 0.5, 1.5, -1.0], dtype=np.float32)
    donor_logits = np.asarray([0.0, 1.9, 1.1, -1.0], dtype=np.float32)
    common = {
        "model": FIXTURE_MODEL,
        "site": "layer_input",
        "layer": 5,
        "sequence_id": "causal-fixture",
        "position": 12,
        "prompt_sha256": _prompt_digest(),
        "executed": True,
        "capture_id": "fixture-paired-capture",
    }
    pair = CausalPair(
        baseline=OutputSnapshot(
            logits=baseline_logits,
            route="activation-space-counterfactual",
            **common,
        ),
        lesion=OutputSnapshot(
            logits=lesion_logits,
            route="activation-space-counterfactual",
            **common,
        ),
        donor=OutputSnapshot(
            logits=donor_logits,
            route="activation-space-counterfactual",
            **common,
        ),
    )
    return pair.assess()


def run(root: Path) -> dict[str, Any]:
    profile = AcquisitionProfile(
        wave_width=512,
        payload_limit=16,
        trace_horizon=2,
        minimum_score=0.58,
        minimum_margin=0.08,
    )
    training_trace = _trace(
        [0.25, -0.5, 0.75, 1.25, -1.5, 0.125, 0.875, -0.25],
        sequence_id="training-episode",
        position=10,
    )
    held_out_trace = _trace(
        [-2.0, 1.0, 0.5, -0.125, 1.75, -0.75, 0.375, 0.625],
        sequence_id="held-out-episode",
        position=11,
    )
    question = "What correction should be emitted for this arithmetic state?"
    meaning = {
        "kind": "model-correction",
        "next_token_id": 42,
        "text": "42",
        "rule": "quotient correction is the field-owned answer",
        "evidence": "teacher-labelled held-out target",
    }
    with UniversalLLMInterpreter(root, model=FIXTURE_MODEL, profile=profile) as interpreter:
        inspection = interpreter.inspect(training_trace)
        state_before = interpreter.state_receipt()
        learning = interpreter.learn(
            training_trace,
            question=question,
            meaning=meaning,
        )
        state_after_learning = interpreter.state_receipt()
        query = interpreter.query(held_out_trace, question=question)
        explanation = interpreter.explain(held_out_trace, question=question)
        weight = WeightSlice.from_array(
            np.asarray([[0.25, -0.5], [0.75, 1.25]], dtype=np.float32),
            model=FIXTURE_MODEL,
            tensor_name="fixture.output.weight",
            tensor_shape=(16, 8),
            row_start=3,
            column_start=4,
        )
        causal = _causal_fixture()
        ownership = interpreter.ownership_receipt()
        field_state_before_close = interpreter.store.learner.fingerprint()

    with UniversalLLMInterpreter(root, model=FIXTURE_MODEL, profile=profile) as restarted:
        restarted_state = restarted.state_receipt()
        restart_query = restarted.query(held_out_trace, question=question)
        field_state_after_restart_query = restarted.store.learner.fingerprint()

    checks = {
        "inspection_non_mutating": state_before["field_state_sha256"]
        == inspection["field_state_sha256"],
        "field_prediction_supported": query["status"] == "field-owned",
        "field_prediction_matches_target": query["prediction"]["target_token_match"] is True,
        "restart_preserves_field": field_state_before_close
        == restarted_state["field_state_sha256"]
        == field_state_after_restart_query,
        "restart_replays_meaning": restart_query["prediction"]["meaning"] == meaning,
        "weight_slice_bounded": weight.values.shape == (2, 2)
        and weight.raw_bytes_touched == 16,
        "causal_boundary_honest": causal["status"] == "counterfactual-only"
        and causal["graph_native_executed"] is False,
        "no_native_fallback": query["native_fallback"] is False,
    }
    body: dict[str, Any] = {
        "schema": "cassi.universal-llm-interpreter-demo.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "model": FIXTURE_MODEL.as_dict(),
        "profile": profile.as_dict(),
        "question": question,
        "program_dimensions": {
            "observatory": "activation trace + model readout + bounded weight slice",
            "translation": "fixed adapter coordinate codec",
            "field_learning": "one QiFieldState.field via raw-event learner",
            "causal_reading": "paired baseline/lesion/donor receipt",
            "correction_delivery": "field-owned deterministic boundary",
            "persistence": "atomic generation checkpoint and journal",
            "explanation": "trace/state/field evidence-linked structure",
            "native_displacement": "not exercised by this offline path",
        },
        "inspection": inspection,
        "learning": learning,
        "state_before_learning": state_before,
        "state_after_learning": state_after_learning,
        "query": query,
        "explanation": explanation,
        "restart_query": restart_query,
        "restarted_state": restarted_state,
        "weight_slice": weight.as_dict(),
        "causal_pair": causal,
        "ownership": ownership,
        "checks": checks,
    }
    body["content_sha256"] = receipt_digest(body)
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        help="persistent field directory; defaults to a temporary run directory",
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
        args.root.mkdir(parents=True, exist_ok=True)
        receipt = run(args.root)
    else:
        with tempfile.TemporaryDirectory(prefix="cassi-universal-interpreter-") as directory:
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
