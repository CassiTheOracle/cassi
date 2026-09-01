from __future__ import annotations

import hashlib
import io

import pytest
import torch
from torch import Tensor

from cassi_text_codec import CassiFieldTextCodec
from cassi_phi_harmonic_attractor_field import PhiHarmonicAttractorFieldConfig
from cassi_phi_harmonic_language import (
    _STATE_FRAME_MAGIC,
    PhiHarmonicLanguageConfig,
    PhiHarmonicLanguageController,
    PHI_HARMONIC_TEXT_RECEIPT_SCHEMA,
    PhiHarmonicTextEngine,
)
from cassi_qi_field import QiFieldError, QiFieldState

MODE_COUNT = 520
TRAINING_EVENTS = (258, 97, 256, 259, 98, 256)
EXPECTED_PORTS = (259, 98, 256)


def _sha256(tensor: Tensor) -> str:
    value = tensor.detach().cpu().contiguous()
    return hashlib.sha256(value.numpy().tobytes(order="C")).hexdigest()


def _tape(controller: PhiHarmonicLanguageController, state: QiFieldState) -> Tensor:
    packed = state.field.reshape(
        controller.config.bank_count,
        9,
        controller.config.mode_count,
        state.batch_size,
    )
    return packed[:, 2:4, controller.config.wave_mode_count :]


def _read_next(
    controller: PhiHarmonicLanguageController,
    state: QiFieldState,
    expected: int,
) -> None:
    before = _sha256(state.field)
    scores = controller.next_symbol_scores(state)
    assert _sha256(state.field) == before
    assert int(scores.argmax(dim=1).item()) == expected


def _run_ports(
    controller: PhiHarmonicLanguageController,
    state: QiFieldState,
    learned_tape_sha256: str,
) -> tuple[int, ...]:
    observed: list[int] = []
    state = controller.sense_user_message(state, "a")
    assert _sha256(_tape(controller, state)) == learned_tape_sha256
    _read_next(controller, state, EXPECTED_PORTS[0])
    observed.append(EXPECTED_PORTS[0])

    for sensed, expected in zip(EXPECTED_PORTS[:2], EXPECTED_PORTS[1:]):
        state = controller.sense_symbol(state, sensed)
        assert _sha256(_tape(controller, state)) == learned_tape_sha256
        _read_next(controller, state, expected)
        observed.append(expected)
    return tuple(observed)


def test_field_tape_learns_and_reinstantiates_next_symbol_scoring() -> None:
    torch.set_num_threads(1)
    config = PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    controller = PhiHarmonicLanguageController(config)
    initial = controller.new_state(batch_size=1, dtype=torch.float64)
    initial_sha256 = _sha256(initial.field)
    learned = controller.learn_exchange(initial, b"a", b"b")

    assert _sha256(initial.field) == initial_sha256
    assert controller.config_fingerprint == config.fingerprint
    assert config.fingerprint != PhiHarmonicAttractorFieldConfig(
        mode_count=MODE_COUNT
    ).fingerprint

    tape_scores, occupied = controller._tape_scores(learned)
    assert tuple(tape_scores[0, :6].argmax(dim=1).tolist()) == TRAINING_EVENTS
    assert bool(occupied[0, :6].all().item())
    assert not bool(occupied[0, 6:].any().item())
    learned_tape_sha256 = _sha256(_tape(controller, learned))

    coordinates = controller._active_coordinates(learned)
    replaced = controller._replace_coordinates(learned, *coordinates)
    bounded = controller._bound(learned)[0]
    evolved = controller.evolve(learned, steps=8)
    for preserved in (replaced, bounded, evolved):
        assert _sha256(_tape(controller, preserved)) == learned_tape_sha256

    invalid_field = learned.field.detach().clone()
    invalid_packed = invalid_field.reshape(
        config.bank_count, 9, config.mode_count, learned.batch_size
    )
    invalid_packed[:, 1, config.wave_mode_count] = 1.0
    with pytest.raises(QiFieldError, match="only trajectory tape planes 2/3"):
        controller.white_readout(QiFieldState(invalid_field))

    oversized_field = learned.field.detach().clone()
    oversized_packed = oversized_field.reshape(
        config.bank_count, 9, config.mode_count, learned.batch_size
    )
    oversized_packed[:, 2, config.wave_mode_count] = (
        config.max_mode_amplitude + 1.0
    )
    with pytest.raises(QiFieldError, match="trajectory tape exceeds"):
        controller.white_readout(QiFieldState(oversized_field))

    learned_tensor = learned.field.detach().clone()
    first = _run_ports(
        controller,
        QiFieldState(learned_tensor.clone()),
        learned_tape_sha256,
    )
    fresh = PhiHarmonicLanguageController(config)
    second = _run_ports(
        fresh,
        QiFieldState(learned_tensor.clone()),
        learned_tape_sha256,
    )
    assert first == second == EXPECTED_PORTS


@pytest.mark.parametrize("dtype", (torch.float32, torch.float64))
def test_trajectory_tape_uses_all_harmonic_lanes_and_replaces_exchange(
    dtype: torch.dtype,
) -> None:
    torch.set_num_threads(1)
    config = PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    controller = PhiHarmonicLanguageController(config)
    codec = CassiFieldTextCodec()
    initial = controller.new_state(batch_size=1, dtype=dtype)

    assert config.trajectory_capacity == 7 * config.wave_mode_count
    boundary_events = codec.encode_training_exchange(b"abcdef", b"g")
    learned = controller.learn_exchange(initial, b"abcdef", b"g")
    scores, occupied = controller._tape_scores(learned)
    assert tuple(
        scores[0, : len(boundary_events)].argmax(dim=1).tolist()
    ) == boundary_events
    assert bool(occupied[0, : len(boundary_events)].all().item())
    assert not bool(occupied[0, len(boundary_events) :].any().item())

    replacement_events = codec.encode_training_exchange(b"x", b"y")
    replaced = controller.learn_exchange(learned, b"x", b"y")
    replacement_scores, replacement_occupied = controller._tape_scores(replaced)
    assert tuple(
        replacement_scores[0, : len(replacement_events)].argmax(dim=1).tolist()
    ) == replacement_events
    assert bool(
        replacement_occupied[0, : len(replacement_events)].all().item()
    )
    assert not bool(
        replacement_occupied[0, len(replacement_events) :].any().item()
    )

    oversized_prompt = b"a" * (config.trajectory_capacity - 4)
    assert (
        len(codec.encode_training_exchange(oversized_prompt, b"b"))
        == config.trajectory_capacity + 1
    )
    with pytest.raises(QiFieldError, match="exceeds trajectory tape capacity"):
        controller.learn_exchange(initial, oversized_prompt, b"b")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required")
def test_gpu_trajectory_writes_replay_bit_exact() -> None:
    config = PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    controller = PhiHarmonicLanguageController(config)
    initial = controller.new_state(device="cuda", dtype=torch.float32)
    prompt = bytes(range(256)) * 4

    hashes = {
        controller.state_sha256(
            controller.learn_exchange(initial, prompt, b"stable")
        )
        for _ in range(8)
    }

    assert len(hashes) == 1


def test_multiple_exchanges_generate_and_latest_correction_wins() -> None:
    torch.set_num_threads(1)
    config = PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    controller = PhiHarmonicLanguageController(config)
    codec = CassiFieldTextCodec()
    initial = controller.new_state(batch_size=1, dtype=torch.float32)
    initial_sha256 = _sha256(initial.field)
    exchanges = ((b"red", b"warm"), (b"blue", b"cool"))
    expected_events = tuple(
        event
        for prompt, continuation in exchanges
        for event in codec.encode_training_exchange(prompt, continuation)
    )

    learned = controller.learn_exchanges(initial, exchanges)
    assert controller.learned_exchanges(learned) == exchanges
    assert _sha256(initial.field) == initial_sha256
    scores, occupied = controller._tape_scores(learned)
    assert tuple(
        scores[0, : len(expected_events)].argmax(dim=1).tolist()
    ) == expected_events
    assert bool(occupied[0, : len(expected_events)].all().item())
    assert not bool(occupied[0, len(expected_events) :].any().item())
    learned_tape_sha256 = _sha256(_tape(controller, learned))

    after_red, red_reply = controller.generate_reply(learned, "red")
    assert red_reply == "warm"
    assert _sha256(_tape(controller, after_red)) == learned_tape_sha256
    after_blue, blue_reply = controller.generate_reply(after_red, "blue")
    assert blue_reply == "cool"
    assert _sha256(_tape(controller, after_blue)) == learned_tape_sha256

    corrected = controller.append_exchange(after_blue, b"red", b"hot")
    corrected_events = (
        *expected_events,
        *codec.encode_training_exchange(b"red", b"hot"),
    )
    assert controller.learned_exchanges(corrected) == (
        *exchanges,
        (b"red", b"hot"),
    )
    corrected_scores, corrected_occupied = controller._tape_scores(corrected)
    assert tuple(
        corrected_scores[0, : len(corrected_events)].argmax(dim=1).tolist()
    ) == corrected_events
    assert bool(corrected_occupied[0, : len(corrected_events)].all().item())
    assert not bool(corrected_occupied[0, len(corrected_events) :].any().item())

    corrected_tensor = corrected.field.detach().clone()
    fresh = PhiHarmonicLanguageController(config)
    restarted, corrected_reply = fresh.generate_reply(
        QiFieldState(corrected_tensor), "red"
    )
    assert corrected_reply == "hot"
    restarted, preserved_reply = fresh.generate_reply(restarted, "blue")
    assert preserved_reply == "cool"
    assert _sha256(_tape(fresh, restarted)) == _sha256(
        _tape(controller, corrected)
    )

    partial_state, partial_reply = controller.generate_reply(
        learned, "red", max_output_symbols=2
    )
    assert partial_reply == "wa"
    assert _sha256(_tape(controller, partial_state)) == learned_tape_sha256


def test_batched_candidate_work_matches_independent_field_branches_exactly() -> None:
    torch.set_num_threads(1)
    controller = PhiHarmonicLanguageController(
        PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    )
    state = controller.learn_exchanges(
        controller.new_state(batch_size=1, dtype=torch.float64),
        ((b"weather", b"warm"), (b"weather", b"windy")),
    )
    before = controller.state_sha256(state)
    candidates = (b"cold", b"warm", b"w", b"windy")

    batched = controller.batch_candidate_sequence_work(
        state, b"weather", candidates
    )
    serial = torch.cat(
        [
            controller.batch_candidate_sequence_work(
                state, b"weather", (candidate,)
            )
            for candidate in candidates
        ]
    )

    assert torch.equal(batched, serial)
    assert int(batched.argmax().item()) == 3
    assert float(batched[1]) > float(batched[0])
    assert controller.state_sha256(state) == before


def test_tape_symbol_signature_is_injective_across_physical_modes() -> None:
    torch.set_num_threads(1)
    config = PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    controller = PhiHarmonicLanguageController(config)
    codec = CassiFieldTextCodec()
    prompt = bytes(range(256))
    continuation = bytes(reversed(range(256)))
    events = codec.encode_training_exchange(prompt, continuation)

    learned = controller.learn_exchange(
        controller.new_state(batch_size=1, dtype=torch.float32),
        prompt,
        continuation,
    )
    scores, occupied = controller._tape_scores(learned)
    assert tuple(scores[0, : len(events)].argmax(dim=1).tolist()) == events
    assert int(torch.count_nonzero(occupied).item()) == len(events)


def test_native_text_engine_roundtrips_tensor_checkpoint_and_receipt() -> None:
    torch.set_num_threads(1)
    config = PhiHarmonicLanguageConfig(mode_count=MODE_COUNT)
    controller = PhiHarmonicLanguageController(config)
    codec = CassiFieldTextCodec()
    learned = controller.learn_exchanges(
        controller.new_state(batch_size=1, dtype=torch.float32),
        (
            (b"hello", "café".encode("utf-8")),
            (b"status", b"ready"),
        ),
    )
    checkpoint = controller.dump_state_bytes(learned)
    restored = controller.load_state_bytes(checkpoint)
    assert controller.state_sha256(restored) == controller.state_sha256(learned)
    assert controller.tape_sha256(restored) == controller.tape_sha256(learned)

    engine = PhiHarmonicTextEngine(controller, max_output_symbols=16)
    messages = (
        {"role": "system", "content": "answer from the learned field"},
        {"role": "user", "content": "hello"},
    )
    input_sha256 = controller.state_sha256(restored)
    result = engine.generate(restored, messages)
    assert controller.state_sha256(restored) == input_sha256
    assert result.reply == "café"
    assert result.render_text() == ("café", "field")
    assert result.prompt_symbols == codec.encode_messages(messages)
    assert result.output_symbols == (
        *"café".encode("utf-8"),
        codec.end_turn_symbol,
    )
    assert result.stop_reason == "end_turn"
    assert result.initial_state_sha256 == input_sha256
    assert result.final_state_sha256 == controller.state_sha256(result.state)
    assert result.tape_sha256 == controller.tape_sha256(learned)
    receipt = result.receipt_dict()
    assert receipt["schema"] == PHI_HARMONIC_TEXT_RECEIPT_SCHEMA
    assert receipt["engine_fingerprint"] == engine.fingerprint
    assert len(result.receipt_sha256) == 64

    successor_checkpoint = controller.dump_state_bytes(result.state)
    fresh_controller = PhiHarmonicLanguageController(config)
    restarted = fresh_controller.load_state_bytes(successor_checkpoint)
    fresh_engine = PhiHarmonicTextEngine(
        fresh_controller, max_output_symbols=16
    )
    restarted_result = fresh_engine.generate(
        restarted,
        ({"role": "user", "content": "status"},),
    )
    assert restarted_result.reply == "ready"
    assert fresh_controller.tape_sha256(restarted_result.state) == result.tape_sha256

    partial = engine.generate(
        restored,
        ({"role": "user", "content": "hello"},),
        max_output_symbols=4,
    )
    assert partial.reply == "caf"
    assert partial.output_symbols == tuple(b"caf")
    assert partial.stop_reason == "max_output_symbols"
    assert controller.tape_sha256(partial.state) == result.tape_sha256
    assert controller.state_sha256(restored) == input_sha256

    with pytest.raises(QiFieldError, match="frame length"):
        controller.load_state_bytes(checkpoint + b"trailing")
    corrupted = bytearray(checkpoint)
    corrupted[-1] ^= 1
    with pytest.raises(QiFieldError, match="frame checksum"):
        controller.load_state_bytes(corrupted)
    with pytest.raises(QiFieldError, match="frame length"):
        controller.load_state_bytes(checkpoint[:-1])

    archive_offset = (
        len(_STATE_FRAME_MAGIC) + 8 + hashlib.sha256().digest_size
    )
    inner = torch.load(
        io.BytesIO(checkpoint[archive_offset:]), weights_only=True
    )

    def framed_with(field: Tensor) -> bytes:
        malformed = {**inner, "field": field, "state_sha256": "0" * 64}
        buffer = io.BytesIO()
        torch.save(malformed, buffer)
        archive = buffer.getvalue()
        return (
            _STATE_FRAME_MAGIC
            + len(archive).to_bytes(8, "big")
            + hashlib.sha256(archive).digest()
            + archive
        )

    with pytest.raises(QiFieldError, match="float32 or torch.float64"):
        controller.load_state_bytes(framed_with(learned.field.to(torch.bfloat16)))
    incompatible = PhiHarmonicLanguageController(
        PhiHarmonicLanguageConfig(mode_count=MODE_COUNT + 2)
    )
    with pytest.raises(QiFieldError, match="identity mismatch"):
        incompatible.load_state_bytes(checkpoint)
