from __future__ import annotations

import hashlib
import json
from pathlib import Path

from run_cassi_math_milestones import run_benchmark


def test_milestone_benchmark_is_sequential_and_memory_preserving(tmp_path):
    canonical = Path(__file__).with_name("_diag") / "math" / "gsm8k_training_state_2.json"
    assert canonical.is_file()
    state_input = tmp_path / "state-in.json"
    state_input.write_bytes(canonical.read_bytes())
    before = state_input.read_bytes()

    receipt = run_benchmark(state_input)
    by_id = {row["id"]: row for row in receipt["cases"]}

    assert receipt["schema"] == "cassifi.math-milestones.v1"
    assert receipt["state"]["memory_preserved_during_inference"] is True
    assert receipt["next_target"]["level"] == 8
    assert receipt["next_target"]["failed_cases"] == ["m8-linear-algebra"]
    assert len(receipt["roadmap"]) == 27
    assert len(receipt["cases"]) == 36
    assert {row["level"] for row in receipt["cases"]} == set(range(27))
    assert receipt["roadmap"][-1]["capability"] == (
        "calculate and certify successive prime numbers"
    )
    assert receipt["prime_goal"]["terminal_level"] == 26
    assert receipt["prime_goal"]["first_generation_target"] == {
        "inclusive_limit": 1000,
        "expected_prime_count": 168,
        "last_prime": 997,
    }
    assert receipt["state"]["adaptive_changed_keys"] == []
    assert receipt["state"]["benchmark_transitions"] == len(receipt["cases"])
    assert receipt["highest_contiguous_milestone"] == 7
    assert by_id["m1-add"]["passed"] is True
    assert by_id["m1-div"]["learned_exact"] is True
    assert by_id["m2-learned-composition"]["passed"] is True
    assert by_id["m2-exact-composition"]["passed"] is True
    assert by_id["m5-linear-integer"]["passed"] is True
    assert by_id["m6-nonlinear-boundary"]["passed"] is True
    assert by_id["m7-inequality-eval"]["passed"] is True
    assert by_id["m7-linear-inequality"]["passed"] is True
    assert by_id["m26-prime-generation"]["planned"] is True
    assert state_input.read_bytes() == before
    assert hashlib.sha256(before).hexdigest() == receipt["state"]["input_sha256"]
    assert json.loads(state_input.read_text(encoding="utf-8"))["ledger"]["transitions"] == 280
