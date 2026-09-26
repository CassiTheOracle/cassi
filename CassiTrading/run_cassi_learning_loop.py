from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cassi_field_learning import NativeProgramOutcomeLearner
from cassi_learning_loop import ChronologicalLearningLoop, make_outcome
from cassi_market_contracts import Prediction, digest_value
from cassi_trading_foundry import RefinementField


RUNNER_SCHEMA = "cassi.market-learning-loop-run.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Cassi chronological prediction/outcome loop")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-learning-loop-v1.json"))
    args = parser.parse_args()

    field = RefinementField()
    field_before = field.fingerprint()
    prediction = Prediction(
        prediction_id="prediction-demo-1",
        predecessor_field_sha256=field_before,
        policy_id="demo-policy",
        program_id="synth-demo-program",
        input_event_ids=("event-demo-1",),
        available_at="2025-01-01T00:00:00Z",
        predicted_outcome={"return": 0.02, "field_signature": "edge"},
        alternatives=({"return": 0.0},),
        cost_expectation={"bps": 5.0},
        risk_expectation={"drawdown": 0.10},
    )
    learner = NativeProgramOutcomeLearner(field, repeats=1)
    loop = ChronologicalLearningLoop(field_sha256=field_before, learner=learner)
    issued = loop.issue_prediction(prediction)
    outcome = make_outcome(
        prediction,
        outcome_id="outcome-demo-1",
        observed_at="2025-01-02T00:00:00Z",
        realized_outcome={"return": 0.03, "drawdown": 0.04},
        execution_trace={"mode": "shadow", "external_effect": "none"},
        cost_vector={"bps": 6.0},
        source_event_ids=("event-demo-result-1",),
    )
    admitted = loop.settle_outcome(outcome)
    field_after = field.fingerprint()
    checkpoint = field.checkpoint_bytes()
    body = {
        "schema": RUNNER_SCHEMA,
        "issued": issued,
        "admitted": admitted,
        "prediction": prediction.as_dict(),
        "outcome": outcome.as_dict(),
        "field_before_sha256": field_before,
        "field_after_sha256": field_after,
        "field_checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
        "field_checkpoint_bytes": len(checkpoint),
        "snapshot": loop.snapshot(),
    }
    body["content_sha256"] = digest_value(body)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": body["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
