from __future__ import annotations

import hashlib

import numpy as np

from cassi_resident_ngram_training import _projection_for_state
from programs.model.ngram_learning import FEEDBACK_SCHEMA, initial_state, learn


def test_nonempty_training_projection_uses_frozen_head_and_learned_readout() -> None:
    hidden = np.array([1.0, 0.5, -0.5, 0.25], dtype=np.float32)
    table_a = np.zeros(2560, dtype=np.float32)
    table_b = np.zeros(2560, dtype=np.float32)
    table_a[0] = 1.0
    table_b[-1] = 1.0
    state = initial_state("model", "table", width=4, rank=4)
    state = learn(state, table_a, hidden, {
        "schema": FEEDBACK_SCHEMA,
        "id": "observed-train-row",
        "model_id": "model",
        "table_id": "table",
        "context_sha256": hashlib.sha256(b"context").hexdigest(),
        "next_token_id": 1,
        "probability_token_id": 1,
        "competitor_token_id": 2,
        "target_direction": [1.0, 0.0, 0.0, 0.0],
        "advantage": 0.0,
    })
    observations = [
        {"id": "train-a", "split": "train"},
        {"id": "train-b", "split": "train"},
        {"id": "heldout-a", "split": "heldout"},
        {"id": "heldout-b", "split": "heldout"},
    ]
    vectors = (table_a, table_b, table_a, table_b)
    frozen_arrays = {
        row["id"]: {
            "hidden": hidden,
            "table_vector": vector,
            "output_norm": np.ones(4, dtype=np.float32),
            "target_row": np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            "competitor_row": np.zeros(4, dtype=np.float32),
        }
        for row, vector in zip(observations, vectors)
    }
    summaries, arrays = _projection_for_state(
        state=state,
        observations=observations,
        frozen_arrays=frozen_arrays,
        baseline_metrics={row["id"]: {"margin": 0.5} for row in observations},
        split_swaps={
            "train": {"train-a": "train-b", "train-b": "train-a"},
            "heldout": {"heldout-a": "heldout-b", "heldout-b": "heldout-a"},
        },
    )
    for split in ("train", "heldout"):
        assert summaries["splits"][split]["projected_margin"]["count"] == 2
        np.testing.assert_array_equal(arrays[f"{split}_measured_baseline_margin"], [0.5, 0.5])
        assert np.all(np.isfinite(arrays[f"{split}_projected_margin"]))
        assert arrays[f"{split}_projected_margin"][0] > 0.5
        assert arrays[f"{split}_projected_margin"][0] != arrays[f"{split}_table_swapped_margin"][0]
