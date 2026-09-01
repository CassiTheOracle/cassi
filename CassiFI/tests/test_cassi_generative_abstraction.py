from dataclasses import replace
from fractions import Fraction
import json
import struct

import math

import pytest

from cassi_generative_abstraction import (
    AbstractionProgram,
    GenerativeAbstractionController,
    GenerativeAbstractionConfig,
    ObservableEntityFrame,
    ProgramToken,
    evaluate_program,
    generate_candidate_programs,
)
from cassi_qi_field import QiFieldError
from cassi_relational_basis import RelationEntity
from cassi_universal_data import (
    Atom,
    BoundaryIdentity,
    BoundaryPacket,
    CODEC_AUDIO,
    CODEC_CODE,
    CODEC_JSON,
    CODEC_OPAQUE,
    CODEC_RASTER,
    CODEC_TENSOR,
    CODEC_TEXT,
    Collection,
    Event,
    ObservationNode,
    ObservationView,
    QiIngressJournal,
    Relation,
    SourceLocation,
    Tensor,
    UniversalDataError,
    ZERO_SHA256,
    adapt,
    event_view,
)
from run_generative_abstraction import (
    run_generative_abstraction_scenario,
    run_typed_adapter_scenario,
    run_universal_data_field_scenario,
)


def test_generated_abstraction_survives_complete_stress_surface() -> None:
    result = run_generative_abstraction_scenario()

    assert result["result"] == "GENERATIVE_ABSTRACTION_OK"
    assert result["claim"] == "bounded field-generated typed relational abstraction"
    assert result["candidate_count"] == result["grammar_program_count"] == 12
    assert result["breaths"] == 4

    interior = result["interior"]
    assert interior["status"] == "selected"
    assert {
        "ROLE_A",
        "ROLE_B",
        "POSITION",
        "SUBTRACT",
        "PACK4",
    }.issubset(interior["tokens"])
    assert result["cartesian_generated"]["role_equivalence_count"] == 2
    assert result["cartesian_generated"]["candidate_source"] == "bounded_typed_grammar"
    grammar = generate_candidate_programs(GenerativeAbstractionConfig())
    generated_relations = tuple(
        program
        for program in grammar
        if program.regime == "interior"
        and "SUBTRACT" in program.decoded
        and "NORMALIZE" not in program.decoded
    )
    assert len(generated_relations) == 2
    assert interior["program_sha256"] in {
        program.sha256 for program in generated_relations
    }
    assert "TARGET_MINUS_SELF" not in ProgramToken.__members__

    invariance = result["renaming_translation"]
    assert invariance["program_residual"] <= 1.0e-12
    assert invariance["action_consequence_residual"] <= 1.0e-12
    assert result["canonicalization"] == {
        "commutative_hash_equal": True,
        "constant_fold_hash_equal": True,
    }

    each_object = result["each_object"]
    assert each_object["directive_rejected_as_scalar_operand"] is True
    assert each_object["expansion_count"] == 3
    assert each_object["first_observation_has_no_previous"] is True
    assert each_object["candidate_entity_ids"] == [
        "relevant-target",
        "moving-distractor-a",
        "moving-distractor-b",
    ]
    assert each_object["moving_candidate_second_delta"] == pytest.approx([0.08, 0.0])

    stationary = result["stationary_endpoint"]
    assert stationary["historical_status"] == "ambiguous"
    assert stationary["historical_equivalent_count"] > 1
    assert stationary["prospective_status"] == "selected"
    assert stationary["prospective_equivalent_count"] > 1
    assert stationary["execution_residual"] <= 1.0e-12

    moving = result["moving_target"]
    assert moving["temporal_tokens"] == ["ROLE_B", "DELTA", "PACK4"]
    assert moving["status"] == "selected"
    assert moving["execution_residual"] <= 1.0e-12

    noise = result["noise_sweep"]
    assert [row["amplitude"] for row in noise] == [0.0, 0.01, 0.02, 0.03, 0.06]
    assert all(row["status"] == "selected" for row in noise)
    assert all(row["deterministic"] for row in noise)
    assert all(row["true_action_retained"] for row in noise)
    assert [row["equivalent_count"] for row in noise] == sorted(
        row["equivalent_count"] for row in noise
    )
    assert [row["interval_radius"] for row in noise] == sorted(
        row["interval_radius"] for row in noise
    )

    distractors = result["diagnostic_distractors"]
    assert distractors["status"] == "selected"
    assert distractors["selected_index"] == 0
    assert distractors["selected_entity_id"] == "relevant-target"
    assert distractors["equivalent_entity_ids"] == ["relevant-target"]

    hidden = result["hidden_relevance"]
    assert hidden["status"] == "ambiguous"
    assert hidden["selected_index"] is None
    assert hidden["selected_entity_id"] is None
    assert hidden["equivalent_indices"] == [0, 1, 2]
    assert hidden["equivalent_entity_ids"] == ["hidden-a", "hidden-b", "hidden-c"]

    roles = result["roles"]
    assert roles["passive_statuses"] == ["ambiguous"] * 4
    assert roles["interventional_correct"] == roles["interventional_attempts"] == 32
    assert roles["false_confidence"] == 0
    assert roles["statuses"] == {"selected": 32, "ambiguous": 0, "exhausted": 0}

    boundary = result["boundary_composition"]
    assert "CLAMP" in boundary["tokens"]
    assert "ACTION_DELTA" in boundary["tokens"]
    assert boundary["exact"] == boundary["case_count"] == 12
    assert boundary["false_settlements"] == 0
    assert boundary["max_residual"] <= 1.0e-12
    config = GenerativeAbstractionConfig()
    evidence = result["program_evidence"]
    selected_boundary = evidence[str(result["boundary"]["program_id"])]
    headroom = next(
        item
        for item in evidence.values()
        if item["tokens"] == ["ROLE_A", "HEADROOM", "PACK4"]
    )
    assert selected_boundary["outcome"] <= config.max_outcome
    assert selected_boundary["score"] <= config.max_score
    assert selected_boundary["outcome"] < headroom["outcome"]
    assert selected_boundary["score"] < headroom["score"]

    shuffled = result["shuffled_program_control"]
    assert shuffled["changed"] is True
    assert shuffled["selection"]["status"] == "exhausted"
    assert shuffled["field_changed"] is True

    ablations = result["ablations"]
    assert ablations == {
        "evidence_status": "exhausted",
        "evidence_program_changed": True,
        "operators_supported": False,
        "operator_trajectory_status": "exhausted",
    }
    consolidation = result["consolidation"]
    assert consolidation == {
        "confirmed": True,
        "count_before": 0,
        "count_after": 1,
        "failed_confirmed": False,
        "failed_field_unchanged": True,
    }
    assert result["restart"] == {
        "bytes_exact": True,
        "field_exact": True,
        "inference_frozen": True,
    }
    assert result["controls"] == {
        "teacher_or_model_calls": 0,
        "live_provider_route": False,
        "provider_rejection": "counterflow request mode must be plan or predict",
        "adaptive_persistent_objects": ["QiFieldState.field"],
    }


def test_interpreter_canonicalizes_and_rejects_invalid_stacks() -> None:
    left = AbstractionProgram(
        (
            ProgramToken.ROLE_A,
            ProgramToken.POSITION,
            ProgramToken.ROLE_B,
            ProgramToken.POSITION,
            ProgramToken.ADD,
            ProgramToken.PACK4,
        )
    )
    right = AbstractionProgram(
        (
            ProgramToken.ROLE_B,
            ProgramToken.POSITION,
            ProgramToken.ROLE_A,
            ProgramToken.POSITION,
            ProgramToken.ADD,
            ProgramToken.PACK4,
        )
    )
    assert left.tokens == right.tokens
    assert left.sha256 == right.sha256

    folded = AbstractionProgram(
        (
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ONE,
            ProgramToken.ADD,
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ZERO,
            ProgramToken.PACK4,
        )
    )
    assert folded.tokens == (
        ProgramToken.CONST_ONE,
        ProgramToken.CONST_ZERO,
        ProgramToken.CONST_ZERO,
        ProgramToken.CONST_ZERO,
        ProgramToken.PACK4,
    )

    with pytest.raises(QiFieldError, match="exactly one vec4"):
        AbstractionProgram((ProgramToken.ROLE_A, ProgramToken.POSITION))
    with pytest.raises(QiFieldError, match="EACH_OBJECT expands observable hypotheses"):
        AbstractionProgram(
            (
                ProgramToken.EACH_OBJECT,
                ProgramToken.POSITION,
                ProgramToken.PACK4,
            )
        )


def test_each_object_expansion_preserves_missing_history_then_temporal_delta() -> None:
    controller = GenerativeAbstractionController()
    frames = (
        ObservableEntityFrame(
            world_id="world",
            episode_id="episode",
            state_sha256="1" * 64,
            regime="interior",
            self_entity=RelationEntity("self", 0.0, 0.0),
            objects=(
                RelationEntity("a", 0.2, -0.1),
                RelationEntity("b", -0.3, 0.4),
            ),
        ),
        ObservableEntityFrame(
            world_id="world",
            episode_id="episode",
            state_sha256="2" * 64,
            regime="interior",
            self_entity=RelationEntity("self", 0.08, 0.0),
            objects=(
                RelationEntity("a", 0.2, -0.1),
                RelationEntity("b", -0.25, 0.38),
            ),
        ),
    )
    hypotheses = controller.expand_each_object(frames)
    assert [item.entity_id for item in hypotheses] == ["a", "b"]
    assert all(item.contexts[0].previous is None for item in hypotheses)
    assert all(item.contexts[1].previous is not None for item in hypotheses)

    temporal = AbstractionProgram(
        (ProgramToken.ROLE_B, ProgramToken.DELTA, ProgramToken.PACK4)
    )
    stationary = evaluate_program(temporal, hypotheses[0].contexts[1]).real.tolist()
    moving = evaluate_program(temporal, hypotheses[1].contexts[1]).real.tolist()
    assert stationary == pytest.approx([0.0, 0.0, 1.0, 0.0])
    assert moving == pytest.approx([0.05, -0.02, 1.0, -0.001])
    assert all(math.isfinite(value) for value in moving)


def _boundary_packet(
    *,
    codec_id: str,
    payload: bytes,
    shape: tuple[int, ...],
    dtype: str,
    head: str = ZERO_SHA256,
    sequence: int = 0,
    stream: str = "test-stream",
    valid: bool = True,
) -> BoundaryPacket:
    return BoundaryPacket.create(
        identity=BoundaryIdentity(
            run_id="universal-test",
            episode_id=f"episode-{stream}-{sequence}",
            world_id="universal-test-world",
            session_id="universal-test-session",
            profile_sha256="1" * 64,
            clock_sha256="2" * 64,
            source_epoch="fixture-v1",
            source_stream_id=stream,
            body_frame_id="test-frame",
        ),
        codec_id=codec_id,
        request_id=f"request-{stream}-{sequence}",
        logical_tick=sequence,
        logical_time=Fraction(sequence, 1),
        capture_start=Fraction(sequence, 1),
        capture_end=Fraction(sequence, 1),
        source_sequence=sequence,
        payload_shape=shape,
        payload_dtype=dtype,
        payload=payload,
        ingress_journal_sha256=head,
        valid=valid,
    )


def _observation_nodes(root: ObservationNode) -> tuple[ObservationNode, ...]:
    nodes: list[ObservationNode] = []

    def visit(node: ObservationNode) -> None:
        nodes.append(node)
        if isinstance(node, Collection):
            for _, child in node.items:
                visit(child)
        elif isinstance(node, Event):
            visit(node.operation)

    visit(root)
    return tuple(nodes)


def test_boundary_packet_and_journal_are_exact_restartable_and_bounded(
    tmp_path,
) -> None:
    payload = json.dumps(
        {"items": [1, True, "λ"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    packet = _boundary_packet(
        codec_id=CODEC_JSON,
        payload=payload,
        shape=(len(payload),),
        dtype="uint8",
    )
    duplicate = _boundary_packet(
        codec_id=CODEC_JSON,
        payload=payload,
        shape=(len(payload),),
        dtype="uint8",
    )
    assert packet == duplicate
    assert packet.packet_sha256 == duplicate.packet_sha256
    assert packet.event_id == duplicate.event_id
    with pytest.raises(UniversalDataError, match="payload digest"):
        replace(packet, payload=b"tampered")
    with pytest.raises(UniversalDataError, match="event identity"):
        replace(packet, request_id="tampered-request")

    journal = QiIngressJournal(tmp_path / "journal", max_bytes=64 * 1024)
    first = journal.append(packet)
    assert journal.append(packet) == first
    second_packet = _boundary_packet(
        codec_id=CODEC_JSON,
        payload=b"[]",
        shape=(2,),
        dtype="uint8",
        head=journal.head_sha256,
        sequence=1,
    )
    second = journal.append(second_packet)
    replayed = QiIngressJournal(tmp_path / "journal", max_bytes=64 * 1024)
    assert replayed.replay() == (first, second)
    assert replayed.read_packet(first) == packet
    assert replayed.read_payload(first) == payload
    assert replayed.read_packet(second) == second_packet

    stale_sequence = _boundary_packet(
        codec_id=CODEC_JSON,
        payload=b"{}",
        shape=(2,),
        dtype="uint8",
        head=journal.head_sha256,
        sequence=1,
    )
    with pytest.raises(UniversalDataError, match="strictly increasing"):
        journal.append(stale_sequence)

    bounded = QiIngressJournal(tmp_path / "bounded", max_bytes=1)
    with pytest.raises(UniversalDataError, match="capacity"):
        bounded.append(packet)
    assert bounded.head_sha256 == ZERO_SHA256
    assert not tuple(bounded.objects.iterdir())
    assert not tuple(bounded.blobs.iterdir())


@pytest.mark.parametrize(
    ("codec_id", "payload", "dtype", "shape", "root_type"),
    (
        (CODEC_JSON, b'{"a":[1,true]}', "uint8", (14,), Collection),
        (CODEC_RASTER, bytes((0, 1, 2, 3)), "uint8", (2, 2), Tensor),
        (CODEC_TEXT, "field λ".encode("utf-8"), "uint8", (8,), Atom),
        (
            CODEC_CODE,
            b"def value():\n    return 1\n",
            "uint8",
            (26,),
            Collection,
        ),
        (
            CODEC_AUDIO,
            struct.pack("<4d", -1.0, -0.25, 0.25, 1.0),
            "float64",
            (2, 2),
            Tensor,
        ),
        (
            CODEC_TENSOR,
            struct.pack("<4f", 1.0, 2.0, 3.0, 4.0),
            "float32",
            (2, 2),
            Tensor,
        ),
        (CODEC_OPAQUE, b"\x00\xff\x10", "uint8", (3,), Atom),
    ),
)
def test_every_adapter_round_trips_deterministically_with_exact_provenance(
    codec_id,
    payload,
    dtype,
    shape,
    root_type,
) -> None:
    packet = _boundary_packet(
        codec_id=codec_id,
        payload=payload,
        shape=shape,
        dtype=dtype,
        stream=codec_id,
    )
    first = adapt(packet, codec_id).require_selected()
    second = adapt(packet, codec_id).require_selected()
    assert isinstance(first.root, root_type)
    assert first.round_trip() == payload
    assert first.view_sha256 == second.view_sha256
    assert all(
        node.source.packet_sha256 == packet.packet_sha256
        and node.source.codec_id == codec_id
        for node in _observation_nodes(first.root)
    )
    if isinstance(first.root, Tensor):
        assert first.root.block_sha256 == packet.payload_sha256
        assert len(_observation_nodes(first.root)) == 1


def test_five_view_constructors_validate_provenance_and_events() -> None:
    packet = _boundary_packet(
        codec_id=CODEC_JSON,
        payload=b"{}",
        shape=(2,),
        dtype="uint8",
    )
    root_source = SourceLocation(packet.packet_sha256, CODEC_JSON)
    atom = Atom(
        SourceLocation(packet.packet_sha256, CODEC_JSON, ("value",)),
        "int",
        1,
    )
    relation = Relation(
        SourceLocation(packet.packet_sha256, CODEC_JSON, ("edge",)),
        "reference",
        ("value",),
        ("value",),
    )
    collection = Collection(
        root_source,
        "map",
        (("value", atom), ("edge", relation)),
    )
    structured = ObservationView(packet, CODEC_JSON, "json", collection)
    action = Atom(
        SourceLocation(packet.packet_sha256, CODEC_JSON, ("operation",)),
        "int",
        0,
    )
    event = event_view(
        packet=packet,
        codec_id=CODEC_JSON,
        before=structured,
        operation=action,
        after=structured,
    ).require_selected()
    tensor_packet = _boundary_packet(
        codec_id=CODEC_RASTER,
        payload=b"\x00\x01\x02\x03",
        shape=(2, 2),
        dtype="uint8",
        stream="tensor",
    )
    tensor = adapt(tensor_packet, CODEC_RASTER).require_selected()
    constructors = {
        type(node).__name__
        for view in (structured, event, tensor)
        for node in _observation_nodes(view.root)
    }
    assert constructors == {"Atom", "Collection", "Tensor", "Relation", "Event"}
    with pytest.raises(UniversalDataError, match="provenance"):
        ObservationView(
            packet,
            CODEC_JSON,
            "json",
            Atom(
                SourceLocation("3" * 64, CODEC_JSON),
                "int",
                1,
            ),
        )


def test_typed_adapter_scenario_reports_only_measured_syntax() -> None:
    result = run_typed_adapter_scenario()
    assert result["result"] == "TYPED_ADAPTER_CONFORMANCE_OK"
    assert set(result["modalities"]) == {
        "text",
        "code",
        "audio",
        "scientific_tensor",
        "opaque",
    }
    assert all(
        row["adapter_status"] == "selected"
        and row["round_trip_exact"]
        and row["provenance_exact"]
        and row["semantic_status"] == "unsupported"
        for row in result["modalities"].values()
    )
    assert result["modalities"]["audio"]["block_backed"] is True
    assert result["modalities"]["scientific_tensor"]["block_backed"] is True
    assert all(
        result["modalities"][name]["block_backed"] is False
        for name in ("text", "code", "opaque")
    )
    assert set(result["controls"]["malformed"].values()) == {"malformed_input"}
    assert result["controls"]["unknown_codec"] == "no_adapter"
    assert result["controls"]["descriptor_mismatch"] == "descriptor_mismatch"
    assert result["controls"]["no_sample"] == "invalid_or_no_sample"
    assert result["journal"] == {
        "entries": 5,
        "replay_exact": True,
        "idempotent": True,
        "one_ingress_interface": "adapt",
    }


def test_universal_json_raster_field_scenario_proves_declared_controls() -> None:
    result = run_universal_data_field_scenario()
    assert result["result"] == "UNIVERSAL_DATA_FIELD_OK"
    assert result["experience_pairs"] == 32
    assert result["experience_views"] == result["experience_exact"] == 64
    assert result["experience_max_residual"] <= 1.0e-12
    assert result["heldout_queries"] == result["heldout_exact"] == 32
    assert result["heldout_modalities"] == {"json": 16, "raster": 16}
    assert result["heldout_max_residual"] <= 1.0e-12
    assert result["cross_view_max_residual"] <= 1.0e-12
    assert result["ambiguous_statuses"] == ["ambiguous", "ambiguous"]
    assert result["pairing_controls"] == {
        "shuffled_failed": True,
        "missing_identity_failed": True,
        "hashes_only_failed": True,
    }
    assert set(result["directional_transfer"]) == {
        "json_to_raster",
        "raster_to_json",
    }
    for row in result["directional_transfer"].values():
        assert row["status"] == "supported"
        assert row["source_experience"] == 32
        assert row["heldout_queries"] == row["heldout_exact"] == 16
        assert row["max_residual"] <= 1.0e-12
        assert row["programs_match_paired_field"] is True
    assert result["ablations"] == {
        "evidence_status": "exhausted",
        "operators_supported": False,
    }
    assert all(result["restart"].values())
    assert result["ingress"]["idempotent"] is True
    assert result["controls"] == {
        "teacher_or_model_calls": 0,
        "adaptive_persistent_objects": ["QiFieldState.field"],
    }
