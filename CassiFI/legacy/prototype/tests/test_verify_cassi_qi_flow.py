from __future__ import annotations

import copy
import struct

import pytest

import verify_cassi_qi_flow as verifier


def _fixture_corpus() -> dict[str, object]:
    corpus: dict[str, object] = {
        "schema": verifier.CANONICAL_FIXTURE_SCHEMA,
        "codec_schema": verifier.CANONICAL_CODEC_SCHEMA,
        "fixtures": [
            {
                "fixture_id": fixture_id,
                "payload_base64": payload_base64,
                "expected": expected,
            }
            for fixture_id, payload_base64, expected in verifier._BOOTSTRAP_FIXTURES
        ],
    }
    corpus["self_sha256"] = verifier.canonical_hash(
        corpus, verifier.CANONICAL_FIXTURE_SCHEMA
    )
    return corpus


def _state_bounds() -> dict[str, object]:
    return {
        "component_abs_max": ["f64:3ff0000000000000"] * 9,
        "complex_amplitude_max": ["f64:3ff0000000000000"] * 4,
        "density_max": "f64:3ff0000000000000",
        "epsilon2_ema_max": "f64:3ff0000000000000",
        "inactive_tail_value": "f64:0000000000000000",
    }


def test_independent_codec_replays_the_complete_frozen_fixture_corpus() -> None:
    corpus = _fixture_corpus()

    assert verifier.validate_canonical_fixture_corpus(corpus) == corpus

    reordered = copy.deepcopy(corpus)
    reordered["fixtures"] = list(reversed(reordered["fixtures"]))
    reordered_body = dict(reordered)
    reordered_body.pop("self_sha256")
    reordered["self_sha256"] = verifier.canonical_hash(
        reordered_body, verifier.CANONICAL_FIXTURE_SCHEMA
    )
    with pytest.raises(verifier.VerificationError):
        verifier.validate_canonical_fixture_corpus(reordered)

def _tuple_document(object_schema: str) -> dict[str, object]:
    return {
        "schema": verifier.SCHEMA_DOCUMENT_SCHEMA,
        "object_schema": object_schema,
        "required_keys": ["schema", "shape"],
        "optional_keys": [],
        "nullable_keys": [],
        "properties": {
            "schema": {"type": "enum", "values": [object_schema]},
            "shape": {
                "type": "tuple",
                "items": [
                    {"type": "integer", "minimum": 1, "maximum": 8},
                    {"type": "integer", "minimum": 1, "maximum": 8},
                ],
            },
        },
    }


def test_tuple_descriptors_validate_and_legacy_tuple_items_is_rejected() -> None:
    # A well-formed tuple descriptor validates for any structural document.
    assert verifier._validate_schema_document(
        _tuple_document(verifier.PROFILE_SCHEMA),
        "profile document",
    )["object_schema"] == verifier.PROFILE_SCHEMA
    assert verifier._validate_schema_document(
        _tuple_document("cassi.qi-flow-receipt.v1"),
        "receipt document",
    )["object_schema"] == "cassi.qi-flow-receipt.v1"

    # The retired array-with-tuple_items encoding is no longer a valid descriptor.
    legacy = _tuple_document(verifier.PROFILE_SCHEMA)
    legacy["properties"]["shape"] = {
        "type": "array",
        "min_items": 2,
        "max_items": 2,
        "tuple_items": [
            {"type": "integer", "minimum": 1, "maximum": 8},
            {"type": "integer", "minimum": 1, "maximum": 8},
        ],
    }
    with pytest.raises(verifier.VerificationError):
        verifier._validate_schema_document(legacy, "profile document")


@pytest.mark.parametrize(
    "payload",
    [
        b'{"x":1.0}',
        b'{"x":-0}',
        b'{"x":"f64:8000000000000000"}',
        b'{"x":"f64:3FF0000000000000"}',
        b'{"z":0,"a":0}',
        b'{"x":1,"x":2}',
        b'\xef\xbb\xbf{}',
        b'\xff',
    ],
)
def test_independent_codec_rejects_noncanonical_adversarial_bytes(payload: bytes) -> None:
    with pytest.raises(verifier.VerificationError):
        verifier.canonical_json_loads(payload)


def test_raw_state_rejects_active_negative_zero_epsilon2_ema() -> None:
    raw = struct.pack("<9d", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.0)

    with pytest.raises(verifier.VerificationError):
        verifier._validate_v3_raw_semantics(
            raw,
            dtype_name="float64",
            shape=[1, 9, 1],
            active_counts=[1],
            state_bounds=_state_bounds(),
        )


def test_raw_state_rejects_negative_zero_inactive_tail() -> None:
    raw = struct.pack("<9d", -0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    with pytest.raises(verifier.VerificationError):
        verifier._validate_v3_raw_semantics(
            raw,
            dtype_name="float64",
            shape=[1, 9, 1],
            active_counts=[0],
            state_bounds=_state_bounds(),
        )
