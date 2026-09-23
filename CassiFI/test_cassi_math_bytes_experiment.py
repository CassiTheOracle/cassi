from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cassi_math_language import evaluate, parse_latex
from run_cassi_math_bytes_experiment import (
    generate_byte_equations,
    continue_byte_training,
)


def _content(length: int = 8192) -> bytes:
    return bytes((index * 37 + 11) % 256 for index in range(length))


def test_byte_equation_generation_is_deterministic_and_split_safe():
    generated = generate_byte_equations(
        _content(),
        byte_budget=4096,
        examples_per_operator=2,
        byte_offset=4096,
    )

    train_spans = {
        tuple(row["source_span"]) for row in generated["rows"]["train"]
    }
    holdout_spans = {
        tuple(row["source_span"]) for row in generated["rows"]["holdout"]
    }
    assert generated["byte_offset"] == 4096
    assert generated["train_bytes"] == generated["holdout_bytes"] == 2048
    assert len(train_spans) == len(holdout_spans) == 8
    assert train_spans.isdisjoint(holdout_spans)
    assert {row["operator"] for row in generated["rows"]["train"]} == {
        "add",
        "sub",
        "mul",
        "div",
    }
    for row in [*generated["rows"]["train"], *generated["rows"]["holdout"]]:
        assert str(evaluate(parse_latex(row["latex"]))) == row["expected"]


def test_byte_training_continues_one_persisted_field_instance(tmp_path):
    source = tmp_path / "gsm8k.bin"
    source.write_bytes(_content())
    canonical = Path(__file__).with_name("_diag") / "math" / "gsm8k_pilot_state.json"
    assert canonical.is_file()
    state_input = tmp_path / "state-in.json"
    state_input.write_bytes(canonical.read_bytes())
    state_output = tmp_path / "state-out.json"

    starting = json.loads(state_input.read_text(encoding="utf-8"))
    starting_transitions = starting["ledger"]["transitions"]
    receipt = continue_byte_training(
        source,
        state_input=state_input,
        byte_budget=4096,
        examples_per_operator=2,
        byte_offset=64,
        page_size=8,
        state_output=state_output,
    )

    assert receipt["schema"] == "cassifi.math-byte-training.v2"
    assert "baseline" not in receipt
    assert receipt["continuation"]["starting_transitions"] == starting_transitions
    assert (
        receipt["continuation"]["final_transitions"]
        > receipt["continuation"]["starting_transitions"]
    )
    assert receipt["direct_byte_intake"]["statuses"] == {"supported": 4}
    assert receipt["direct_byte_intake"]["byte_offset"] == 64
    assert receipt["direct_byte_intake"]["observed_bytes"] == 2048
    assert receipt["learning"]["lesson_statuses"] == {
        "add": "supported",
        "div": "supported",
        "mul": "supported",
        "sub": "supported",
    }
    assert receipt["holdout"]["submitted"] == 8
    assert receipt["holdout"]["supported"] == 8
    assert receipt["holdout"]["exact"] == 8
    assert receipt["holdout"]["failure_count"] == 0
    assert receipt["state_checkpoint"] == str(state_output)
    assert json.loads(state_input.read_text(encoding="utf-8")) == starting
    assert (
        json.loads(state_output.read_text(encoding="utf-8"))["ledger"]["transitions"]
        == receipt["continuation"]["final_transitions"]
    )
    assert (
        hashlib.sha256(state_output.read_bytes()).hexdigest()
        == receipt["continuation"]["state_output_sha256"]
    )
