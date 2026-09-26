from __future__ import annotations

import json
import struct

import pytest

from cassi_field_atlas import FieldIntelligenceError
from cassi_field_cognition import semantic_cognition_kernel, semantic_cognition_state
from cassi_field_input import (
    CODEC_AUDIO,
    CODEC_CODE,
    CODEC_JSON,
    CODEC_OPAQUE,
    CODEC_RASTER,
    CODEC_TENSOR,
    CODEC_TEXT,
    SourceViewError,
    source_observation_page,
)
from cassi_field_owner import FieldIntelligenceOwner, SourceInput
from run_cassi_computer import main as computer_cli


def _source(
    content: bytes,
    codec: str,
    *,
    source_id: str = "source-input",
    media_type: str = "application/octet-stream",
) -> SourceInput:
    return SourceInput(
        source_id=source_id,
        content=content,
        media_type=media_type,
        codec=codec,
        observed_timestamp="2026-09-14T00:00:00Z",
        scope="test",
        claim_category="observation",
        fidelity="exact",
    )


def _semantic_step(state, **request):
    transition = semantic_cognition_kernel(state, request, 4096)
    assert transition.status == "done"
    return transition.state, transition.output


def test_fixed_codecs_emit_deterministic_source_linked_pages() -> None:
    fixtures = [
        (_source(b'{"a":[1,true]}', CODEC_JSON, media_type="application/json"), {}),
        (_source("alpha\nβeta".encode(), CODEC_TEXT, media_type="text/plain"), {}),
        (_source(b"x = 1\n", CODEC_CODE, media_type="text/x-python"), {}),
        (_source(b"\x00\xffopaque", CODEC_OPAQUE), {}),
        (
            _source(struct.pack("<ff", 1.5, -2.0), CODEC_TENSOR),
            {"dtype": "f32le", "shape": [2], "units": ["m"]},
        ),
        (
            _source(bytes(range(6)), CODEC_RASTER, media_type="image/raw"),
            {"shape": [1, 2, 3]},
        ),
        (
            _source(struct.pack("<dd", 0.25, -0.5), CODEC_AUDIO, media_type="audio/raw"),
            {"shape": [2], "units": ["amplitude"]},
        ),
    ]
    for source, options in fixtures:
        first = source_observation_page(source, page_size=2, **options)
        second = source_observation_page(source, page_size=2, **options)
        assert first == second
        assert first["status"] == "supported"
        assert first["source_revision_id"] == source.revision_id
        assert first["content_sha256"] == source.revision_identity()["content_sha256"]
        assert 1 <= first["item_count"] <= 2
        assert all(
            row["binding_id"].startswith(f"source:{source.revision_id[:24]}:")
            and row["subject"] == source.source_id
            and "value" in row
            for row in first["observations"]
        )


def test_source_pages_are_bounded_paged_and_fail_closed() -> None:
    source = _source((b"a" * 1024 + b"\n") * 3, CODEC_TEXT, media_type="text/plain")
    first = source_observation_page(source, page_size=1)
    second = source_observation_page(
        source, cursor=first["next_cursor"], page_size=1
    )
    assert first["complete"] is False
    assert first["item_count"] == second["item_count"] == 1
    assert first["observations"] != second["observations"]
    assert source_observation_page(_source(b"x", "unknown-codec"))["status"] == "unsupported"
    assert source_observation_page(_source(b"{", CODEC_JSON))["status"] == "unsupported"
    aliased_json = source_observation_page(
        _source(b'{"alias":true}', "utf-8", media_type="application/json")
    )
    assert aliased_json["status"] == "supported"
    assert aliased_json["decoder_codec"] == CODEC_JSON
    nonfinite_code = source_observation_page(
        _source(b"value = 1e999\n", CODEC_CODE, media_type="text/x-python")
    )
    assert nonfinite_code["status"] == "unsupported"
    malformed_tensor = source_observation_page(
        _source(b"\x00", CODEC_TENSOR), dtype="f64le", shape=[1]
    )
    assert malformed_tensor["status"] == "unsupported"
    with pytest.raises(SourceViewError):
        source_observation_page(source, cursor=99)
    with pytest.raises(SourceViewError):
        source_observation_page(source, page_size=257)


def test_owner_input_initializes_resident_cognition_replays_and_restarts(tmp_path) -> None:
    root = tmp_path / "field"
    source = _source(
        json.dumps({"name": "Cassi", "values": [1, 2]}).encode(),
        CODEC_JSON,
        media_type="application/json",
    )
    with FieldIntelligenceOwner(root) as owner:
        owner.operate_computer(
            "configure-input",
            computer_id="main",
            action="configure",
        )
        result = owner.admit_computer_input(
            "input-json",
            computer_id="main",
            source=source,
            page_size=2,
        )
        assert result["status"] == "supported"
        assert result["computer"]["receipt"]["action"] == "submit"
        assert result["view"]["item_count"] == 2
        task = owner.state.computers[0].inspect()["task"]
        assert task["family"] == "cognition.field"
        assert task["indexes"]["deliveries"]
        generation = owner.state.generation
        state_sha256 = owner.state.state_sha256
        replay = owner.admit_computer_input(
            "input-json",
            computer_id="main",
            source=source,
            page_size=2,
        )
        assert replay["computer"]["checkpoint_receipt"]["replayed"] is True
        with pytest.raises(FieldIntelligenceError) as changed_replay:
            owner.admit_computer_input(
                "input-json",
                computer_id="main",
                source=source,
                page_size=1,
            )
        assert changed_replay.value.code == "OPERATION_CONFLICT"
        assert owner.state.generation == generation
        assert owner.state.state_sha256 == state_sha256
        computer_sha256 = owner.state.computers[0].state_sha256
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == state_sha256
        assert owner.state.computers[0].state_sha256 == computer_sha256
        later = owner.admit_computer_input(
            "input-json-page-2",
            computer_id="main",
            source=source,
            cursor=2,
            page_size=2,
        )
        assert later["computer"]["receipt"]["action"] == "invoke"
        before_unsupported = owner.state.computers[0].state_sha256
        unsupported = owner.admit_computer_input(
            "input-unsupported",
            computer_id="main",
            source=_source(b"raw", "unknown-codec", source_id="raw-source"),
        )
        assert unsupported["status"] == "unsupported"
        assert unsupported["computer"] is None
        assert owner.state.computers[0].state_sha256 == before_unsupported


def test_cli_admits_text_json_tensor_and_opaque_sources(
    tmp_path, capsys
) -> None:
    data_home = tmp_path / "field"
    fixtures = [
        ("text.txt", b"ordinary language", CODEC_TEXT, []),
        (
            "object.json",
            b'{"count":2,"ready":true}',
            CODEC_JSON,
            ["--media-type", "application/json"],
        ),
        (
            "tensor.bin",
            struct.pack("<ff", 1.25, -4.5),
            CODEC_TENSOR,
            ["--dtype", "f32le", "--shape", "2", "--unit", "meters"],
        ),
        ("opaque.bin", b"\x00\xff\x10", CODEC_OPAQUE, []),
    ]
    prefix = ["--data-home", str(data_home)]
    assert computer_cli([*prefix, "configure"]) == 0
    capsys.readouterr()
    admitted: list[tuple[str, bytes]] = []
    for ordinal, (name, content, codec, options) in enumerate(fixtures):
        source_path = tmp_path / name
        source_path.write_bytes(content)
        operation_id = f"cli-input-{ordinal}"
        assert computer_cli(
            [
                *prefix,
                "--operation-id",
                operation_id,
                "input",
                str(source_path),
                "--codec",
                codec,
                "--source-id",
                name,
                *options,
            ]
        ) == 0
        payload = json.loads(capsys.readouterr().out)
        result = payload["response"]["result"]
        assert result["status"] == "supported"
        assert result["view"]["decoder_codec"] == codec
        admitted.append(
            (result["evidence"]["source"]["revision_id"], content)
        )
    with FieldIntelligenceOwner(data_home) as owner:
        for revision_id, content in admitted:
            assert owner.evidence.read(revision_id) == content
        task = owner.state.computers[0].inspect()["task"]
        assert len(task["indexes"]["deliveries"]) == len(fixtures)


def test_autonomous_representation_refines_and_exposes_novel_encoding() -> None:
    state = semantic_cognition_state()
    training = [
        {"example_id": "e0", "features": {"x": 5.0, "y": 2.0}, "outcome": 3.0},
        {"example_id": "e1", "features": {"x": 9.0, "y": 4.0}, "outcome": 5.0},
        {"example_id": "e2", "features": {"x": 7.0, "y": 10.0}, "outcome": -3.0},
        {"example_id": "e3", "features": {"x": 7.0, "y": 12.0}, "outcome": -5.0},
    ]
    holdout = [
        {
            "example_id": "h0",
            "features": {"x": 97.0, "y": 100.0},
            "outcome": -3.0,
            "rare_case": True,
        },
        {
            "example_id": "h1",
            "features": {"x": 205.0, "y": 200.0},
            "outcome": 5.0,
            "rare_case": True,
        },
    ]
    state, learned = _semantic_step(
        state,
        operation="learn-representation",
        operation_id="learn-autonomous-difference",
        representation_id="autonomous-difference",
        examples=training,
        holdout=holdout,
        question={"target": "signed-distance"},
        information_boundary={"available": ["features"]},
    )
    assert learned["status"] == "supported"
    assert learned["selected_candidate"].startswith("auto:difference:")
    assert learned["candidates"]
    state, predictive_gap = _semantic_step(
        state,
        operation="query",
        operation_id="query-autonomous-outcome-gap",
        query={
            "kind": "representation",
            "representation_id": "autonomous-difference",
            "features": {"x": 309.0, "y": 300.0},
        },
    )
    assert predictive_gap["status"] == "support-gap"
    assert "representation-state-unseen" in predictive_gap["limitations"]
    state, encoded = _semantic_step(
        state,
        operation="query",
        operation_id="query-autonomous-encoding",
        query={
            "kind": "representation",
            "representation_id": "autonomous-difference",
            "readout": "encoded",
            "features": {"x": 309.0, "y": 300.0},
        },
    )
    assert encoded["status"] == "supported"
    assert encoded["readout"] == "encoded"
    assert list(encoded["answer"].values()) == [9.0]
    state, revised = _semantic_step(
        state,
        operation="learn-representation",
        operation_id="relearn-autonomous-difference",
        representation_id="autonomous-difference",
        examples=[*training, {"example_id": "e4", "features": {"x": 21.0, "y": 14.0}, "outcome": 7.0}],
        holdout=holdout,
        question={"target": "signed-distance"},
        information_boundary={"available": ["features"]},
    )
    assert revised["representation"]["content_version"] == 2
    with pytest.raises(FieldIntelligenceError) as empty_features:
        _semantic_step(
            semantic_cognition_state(),
            operation="learn-representation",
            operation_id="learn-no-features",
            representation_id="no-features",
            examples=[{"features": {}, "outcome": "none"}],
        )
    assert empty_features.value.code == "INVALID_REPRESENTATION_EVIDENCE"
