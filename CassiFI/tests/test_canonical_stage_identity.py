"""Canonical stage-identity helpers keep the exact digest they replaced.

The owner derives each resident stage's request identity from one canonical
encoding of the request and splices those bytes into the request row, so the
request is encoded once per stage instead of twice.  These tests pin the bytes:
the splice must equal the direct row encoding for the shapes a stage request
and a field row actually take.
"""

import hashlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "CassiFI"))

from cassi_field_atlas import (  # noqa: E402
    _row_bytes,
    canonical_json_bytes,
    canonical_json_field_bytes,
)

STAGE_REQUEST = {
    "operation_id": "qwen-layer-3",
    "stage": "qwen-layer",
    "op": "qwen-layer",
    "inputs": [],
    "output": None,
    "position": 7,
    "parameters": {
        "source_id": "qwen3.5-0.8b",
        "source_sha256": "ab" * 32,
        "manifest_sha256": "cd" * 32,
        "architecture": "qwen35",
        "metadata_sha256": "ef" * 32,
        "trunk_layer_count": 24,
        "layer": 3,
        "recurrent": True,
        "tensor_names": {
            "attn_norm": "blk.3.attn_norm.weight",
            "q": "blk.3.attn_q.weight",
            "k": "blk.3.attn_k.weight",
            "v": "blk.3.attn_v.weight",
            "attn_output": "blk.3.attn_output.weight",
            "attn_gate": "blk.3.attn_gate.weight",
            "ssm_out": "blk.3.ssm_out.weight",
            "ffn_norm": "blk.3.ffn_norm.weight",
            "ffn_gate": "blk.3.ffn_gate.weight",
            "ffn_down": "blk.3.ffn_down.weight",
            "ffn_up": "blk.3.ffn_up.weight",
        },
        "membrane_profile": {"mode_count": 256, "gain_ppm": 5000},
    },
    "state_effects": ["resident-attention-memory", "resident-ffn-memory"],
}

REQUEST_ROW = {
    "kind": "neural-membrane-stage",
    "computer_id": "computer-1",
    "task_id": "task-1",
    "resident_operation_id": "qwen-layer-3",
    "minimum_modes": 256,
    "stage_request": STAGE_REQUEST,
    "resume_task": True,
    "batch_to_token": True,
}


def test_spliced_row_bytes_equal_the_direct_encoding():
    request_bytes = canonical_json_bytes(STAGE_REQUEST)
    assert canonical_json_field_bytes(
        REQUEST_ROW, "stage_request", request_bytes
    ) == canonical_json_bytes(REQUEST_ROW)


@pytest.mark.parametrize(
    "payload",
    [
        {"text": 'a "quoted" \\ value', "empty": "", "list": [1, 2]},
        {"nested": {"deeper": [{"x": None}]}},
        {"floats": [0.0, -0.0, 1.0e-7, -2.5, 2**53 + 1]},
        {"unicode": "✓ λ 漢", "escapes": "\n\t"},
        (1, 2.5),
        [],
        None,
    ],
    ids=["text", "nested", "floats", "unicode", "tuple", "empty-list", "none"],
)
def test_spliced_row_bytes_equal_the_direct_encoding_for_awkward_values(payload):
    row = {"kind": "row", "stage_request": payload, "count": 2}
    assert canonical_json_field_bytes(
        row, "stage_request", canonical_json_bytes(payload)
    ) == canonical_json_bytes(row)


def test_splice_uses_the_fallback_when_the_placeholder_is_absent():
    row = {"kind": "row", "count": 2}
    assert canonical_json_field_bytes(
        row, "stage_request", b'{"a":1}'
    ) == canonical_json_bytes(row)


def test_field_tensor_row_bytes_keep_the_direct_encoding():
    row = {
        "kind": "field",
        "field_b64": "QUJD" * 2000,
        "value_sha256": "ab" * 32,
        "mode_count": 256,
    }
    assert _row_bytes(row) == canonical_json_bytes(row)


def test_short_field_tensor_row_bytes_keep_the_direct_encoding():
    row = {"kind": "field", "field_b64": "QUJD", "mode_count": 256}
    assert _row_bytes(row) == canonical_json_bytes(row)


def test_request_row_digest_is_stable_across_both_encodings():
    request_bytes = canonical_json_bytes(STAGE_REQUEST)
    spliced = hashlib.sha256(
        canonical_json_field_bytes(REQUEST_ROW, "stage_request", request_bytes)
    ).hexdigest()
    direct = hashlib.sha256(canonical_json_bytes(REQUEST_ROW)).hexdigest()
    assert spliced == direct


def test_detached_request_matches_the_canonical_bytes_it_was_decoded_from():
    """The owner hands the executor exactly what the round trip produced."""

    import json

    stage_request_bytes = canonical_json_bytes(dict(STAGE_REQUEST))
    stage_request = json.loads(stage_request_bytes.decode("utf-8"))
    assert canonical_json_bytes(stage_request) == stage_request_bytes
    assert stage_request == STAGE_REQUEST
