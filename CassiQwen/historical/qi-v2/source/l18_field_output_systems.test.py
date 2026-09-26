"""Acceptance tests for the pure L18 field-output systems.

These tests are intentionally small at the system boundary and do not load a
model, DLL, native runtime, or Godot scene.
"""

from __future__ import annotations

import json

import numpy as np

from l18_field_output_systems import (
    DIMENSION,
    GRID_N,
    DecodedFieldMemory,
    JsonlEventWriter,
    TokenLevelPlanner,
    decode_direction_field,
    encode_direction_field,
    field_raw_metadata,
    select_field_language_candidates,
)


def test_direction_fourier_round_trip() -> None:
    source = np.linspace(-1.0, 1.0, DIMENSION, dtype=np.float32)
    encoded = encode_direction_field(source)
    assert encoded.ey.shape == (GRID_N**3,)
    assert encoded.ei.shape == (GRID_N**3,)
    decoded = decode_direction_field(encoded.ey, encoded.ei)
    expected = source.astype(np.float64)
    expected /= np.linalg.norm(expected)
    assert np.allclose(decoded, expected, rtol=0.0, atol=3.0e-6)
    assert np.isfinite(encoded.ey).all()
    assert np.isfinite(encoded.ei).all()


def test_raw_field_metadata_has_stable_shape_and_hashes() -> None:
    ey = np.zeros(GRID_N**3, dtype=np.float32)
    ei = np.ones(GRID_N**3, dtype=np.float32)
    metadata = field_raw_metadata(ey, ei)
    assert metadata["dtype"] == "float32-le"
    assert metadata["shape"] == [GRID_N**3]
    assert metadata["layout"] == "x + N*(y + N*z)"
    assert len(metadata["ey_sha256"]) == 64
    assert len(metadata["ei_b64"]) > 0


def test_memory_retrieval_orders_cosine_then_token_index_and_external() -> None:
    memory = DecodedFieldMemory()
    anchor = np.zeros(DIMENSION, dtype=np.float32)
    anchor[0] = 1.0
    opposite = -anchor
    memory.add(anchor, token_index=2, token_id=22, record_id="later")
    memory.add(anchor, token_index=1, token_id=11, record_id="earlier")
    matches = memory.retrieve(anchor, top_k=3, external_records=[{"record_id": "external", "token_index": 0, "vector": anchor}])
    assert [row["record_id"] for row in matches] == ["earlier", "later", "external"]
    assert matches[0]["score"] == 1.0
    assert memory.retrieve(opposite, top_k=1)[0]["record_id"] == "earlier"


def test_candidate_blend_and_token_id_tie_breaking_are_deterministic() -> None:
    ordinary = np.array([2.0, 1.0, 2.0], dtype=np.float32)
    field = np.array([0.0, 3.0, 2.0], dtype=np.float32)
    result = select_field_language_candidates(ordinary, field, gamma=0.5, enabled=True, top_k=3, token_ids=[9, 4, 7])
    assert [row["token_id"] for row in result["top_k"]] == [4, 7, 9]
    assert np.allclose([row["score"] for row in result["top_k"]], [2.0, 2.0, 1.0])
    ordinary_only = select_field_language_candidates(ordinary, field, gamma=0.5, top_k=3, token_ids=[9, 4, 7])
    assert ordinary_only["token_ids"] == [7, 9, 4]
    assert ordinary_only["gamma"] == 0.0


def test_planner_records_memory_candidate_and_no_external_actions() -> None:
    memory = DecodedFieldMemory()
    planner = TokenLevelPlanner(memory, gamma=0.25, top_k=2, retrieval_k=1, enabled=True)
    vector = np.zeros(DIMENSION, dtype=np.float32)
    vector[0] = 1.0
    first = planner.plan(0, [3.0, 2.0], [0.0, 4.0], decoded_vector=vector, selected_piece="first")
    second = planner.plan(1, [3.0, 2.0], [0.0, 4.0], decoded_vector=vector, selected_piece="second")
    assert first["selected_token_id"] == 1
    assert second["retrieved_memory"][0]["record_id"].startswith("token-0-")
    assert second["selected_piece"] == "second"
    assert second["external_actions"] == []
    assert second["actions"] == []
    assert len(memory.records) == 2


def test_jsonl_event_and_receipt_writer(tmp_path) -> None:
    event_path = tmp_path / "events.jsonl"
    receipt_path = tmp_path / "receipt.json"
    writer = JsonlEventWriter(event_path, receipt_path=receipt_path)
    event_receipt = writer.write_event({"protocol": "test", "token_index": np.int64(0), "finite": True})
    final_receipt = writer.write_receipt({"verdict": "PASS", "event_receipt": event_receipt})
    lines = event_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["token_index"] == 0
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["verdict"] == "PASS"
    assert final_receipt["event_count"] == 1


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    test_direction_fourier_round_trip()
    test_raw_field_metadata_has_stable_shape_and_hashes()
    test_memory_retrieval_orders_cosine_then_token_index_and_external()
    test_candidate_blend_and_token_id_tie_breaking_are_deterministic()
    test_planner_records_memory_candidate_and_no_external_actions()
    with tempfile.TemporaryDirectory() as directory:
        test_jsonl_event_and_receipt_writer(Path(directory))
    print("L18 field-output systems tests passed")
