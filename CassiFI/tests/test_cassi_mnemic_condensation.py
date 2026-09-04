from __future__ import annotations

import hashlib

import pytest
import torch

from cassi_mnemic_condensation import (
    MnemicCondensationConfig,
    MnemicCondensationController,
    mnemic_field_address,
)


def _revision(record_id: str, content: str) -> str:
    return hashlib.sha256(f"{record_id}\0memory\0{content}".encode("utf-8")).hexdigest()


def _records(count: int = 32) -> list[tuple[str, str, str, bytes]]:
    adjectives = (
        "amber", "brisk", "calm", "deep", "ember", "faint", "golden", "hushed",
        "indigo", "jade", "kindred", "lunar", "mellow", "narrow", "opal", "quiet",
        "red", "silver", "tidal", "umber", "violet", "warm", "xenic", "young",
        "zenith", "arc", "bright", "clear", "distant", "even", "fluid", "gentle",
    )
    nouns = (
        "aurora", "beacon", "cedar", "delta", "estuary", "fern", "garden", "harbor",
        "island", "junction", "keystone", "lantern", "meadow", "nebula", "orchard", "pond",
        "quartz", "river", "spiral", "thicket", "upland", "valley", "willow", "xylem",
        "yard", "zephyr", "anchor", "brook", "coral", "dune", "echo", "fjord",
    )
    records: list[tuple[str, str, str, bytes]] = []
    for index in range(count):
        record_id = f"memory-{index:02d}"
        key = f"{adjectives[index]} {nouns[index]}"
        content = f"The {key} marks exact field memory number {index:02d}."
        revision = _revision(record_id, content)
        address = mnemic_field_address(
            record_id,
            revision,
            0,
            len(content.encode("utf-8")),
            "memory",
        )
        records.append((record_id, key, content, address))
    return records


@pytest.mark.parametrize("count", [1, 2])
def test_small_population_layout_and_signal(count: int) -> None:
    controller = MnemicCondensationController(
        MnemicCondensationConfig(cue_dimensions=512, slow_retention=0.99999)
    )
    state = controller.initial_state()
    records = _records(count)
    overlaps: list[float] = []
    for _record_id, key, content, address in records:
        content_vector = controller.cue_vector(
            content,
            device=state.field.device,
            dtype=state.field.dtype,
        )
        query_vector = controller.cue_vector(
            f"please recall the {key}",
            device=state.field.device,
            dtype=state.field.dtype,
        )
        overlaps.append(float((content_vector @ query_vector).item()))
        state, _ = controller.condense(state, cue=content, address=address)
        state, _ = controller.condense(
            state,
            cue=f"remember {key} field memory",
            address=address,
        )

    slow_norm_before = float(controller._differential(state)[-1].norm().item())
    washed = controller.evolve(state, steps=16)
    slow_norm_after = float(controller._differential(washed)[-1].norm().item())
    manifest = [record[3] for record in records]
    results = [
        controller.recall(
            washed,
            f"please recall the {key}",
            candidate_addresses=manifest,
        )
        for _record_id, key, _content, _address in records
    ]
    assert all(
        result.address == record[3]
        for result, record in zip(results, records, strict=True)
    ), (
        f"count={count}; overlap={overlaps}; "
        f"slow_norm={slow_norm_before:.6f}->{slow_norm_after:.6f}; "
        f"signals={[result.signal for result in results]}; "
        f"minimum_margins={[result.minimum_bit_margin for result in results]}"
    )


@pytest.mark.parametrize("cue_dimensions", [256, 512])
def test_partial_cues_condense_to_exact_addresses_and_survive_reload(
    cue_dimensions: int,
) -> None:
    controller = MnemicCondensationController(
        MnemicCondensationConfig(cue_dimensions=cue_dimensions, slow_retention=0.99999)
    )
    state = controller.initial_state(dtype=torch.float32)
    records = _records()

    for _record_id, key, content, address in records:
        state, _ = controller.condense(state, cue=content, address=address)
        # Co-present an ordinary abbreviated observation. The address is opaque;
        # the field, rather than its hash, must acquire this cue association.
        state, _ = controller.condense(
            state,
            cue=f"remember {key} field memory",
            address=address,
        )

    trained_hash = controller.state_sha256(state)
    washed = controller.evolve(state, steps=256)
    assert controller.state_sha256(washed) != trained_hash

    correct = 0
    resolved = 0
    signals: list[float] = []
    for _record_id, key, _content, address in records:
        before = controller.state_sha256(washed)
        recalled = controller.recall(
            washed,
            f"please recall the {key}",
            candidate_addresses=[record[3] for record in records],
        )
        after = controller.state_sha256(washed)
        assert after == before
        signals.append(recalled.signal)
        if recalled.address is not None:
            resolved += 1
        if recalled.address == address:
            correct += 1
    assert correct == len(records), (
        f"exact address recall was {correct}/{len(records)}; "
        f"resolved={resolved}; signal={min(signals):.3f}..{max(signals):.3f}"
    )

    payload = controller.dump_state_bytes(washed)
    restored = controller.load_state_bytes(payload)
    assert controller.state_sha256(restored) == controller.state_sha256(washed)
    for _record_id, key, _content, address in records:
        assert controller.recall(
            restored,
            f"please recall the {key}",
            candidate_addresses=[record[3] for record in records],
        ).address == address


def test_field_only_lesion_removes_recall() -> None:
    controller = MnemicCondensationController()
    state = controller.initial_state()
    record_id = "memory-lesion"
    content = "A copper helix closes around the quiet center."
    address = mnemic_field_address(
        record_id,
        _revision(record_id, content),
        0,
        len(content.encode("utf-8")),
        "memory",
    )
    state, _ = controller.condense(state, cue=content, address=address)
    assert controller.recall(
        state,
        "copper helix quiet center",
        candidate_addresses=[address],
    ).address == address

    lesioned = controller.lesion_slow_field(state)
    recall = controller.recall(
        lesioned,
        "copper helix quiet center",
        candidate_addresses=[address],
    )
    assert recall.address is None
    assert recall.signal == pytest.approx(0.0, abs=1.0e-12)


def test_hash_address_alone_has_no_semantic_recall() -> None:
    controller = MnemicCondensationController()
    state = controller.initial_state()
    record_id = "memory-association"
    content = "The violet river carries a phase-locked signal."
    address = mnemic_field_address(
        record_id,
        _revision(record_id, content),
        0,
        len(content.encode("utf-8")),
        "memory",
    )

    assert controller.recall(
        state,
        "violet river",
        candidate_addresses=[address],
    ).address is None
    state, _ = controller.condense(state, cue=content, address=address)
    assert controller.recall(
        state,
        "violet river phase signal",
        candidate_addresses=[address],
    ).address == address


def test_lexically_disjoint_alias_requires_explicit_field_feedback() -> None:
    controller = MnemicCondensationController()
    state = controller.initial_state()
    record_id = "memory-disjoint-alias"
    content = "The violet river carries a phase-locked signal."
    alias = "purple waterway transmits synchronized information"
    address = mnemic_field_address(
        record_id,
        _revision(record_id, content),
        0,
        len(content.encode("utf-8")),
        "memory",
    )
    state, _ = controller.condense(state, cue=content, address=address)
    assert controller.recall(
        state,
        alias,
        candidate_addresses=[address],
    ).address is None

    state, _ = controller.condense(state, cue=alias, address=address)
    assert controller.recall(
        state,
        alias,
        candidate_addresses=[address],
    ).address == address



def test_fresh_field_no_evolution_and_disjoint_cues_abstain() -> None:
    controller = MnemicCondensationController()
    records = _records(8)
    manifest = [record[3] for record in records]
    fresh = controller.initial_state()

    for _record_id, key, _content, _address in records:
        recall = controller.recall(
            fresh,
            f"please recall the {key}",
            candidate_addresses=manifest,
        )
        assert recall.address is None
        assert recall.signal == pytest.approx(0.0, abs=1.0e-12)

    _record_id, _key, content, address = records[0]
    deposited, _ = controller.deposit(fresh, cue=content, address=address)
    differential = controller._differential(deposited)
    assert float(differential[0].norm().item()) > 0.0
    assert float(differential[-1].norm().item()) == pytest.approx(0.0, abs=1.0e-12)
    assert controller.recall(
        deposited,
        content,
        candidate_addresses=manifest,
    ).address is None

    trained = fresh
    for _record_id, key, content, address in records:
        trained, _ = controller.condense(trained, cue=content, address=address)
        trained, _ = controller.condense(
            trained,
            cue=f"remember {key} field memory",
            address=address,
        )
    disjoint = controller.recall(
        trained,
        "volcanic telescope grammar without a shared memory token",
        candidate_addresses=manifest,
    )
    assert disjoint.address is None


def test_shuffled_address_pairing_follows_the_field_association() -> None:
    controller = MnemicCondensationController(
        MnemicCondensationConfig(cue_dimensions=512, slow_retention=0.99999)
    )
    records = _records(16)
    manifest = [record[3] for record in records]
    shuffled = manifest[1:] + manifest[:1]
    state = controller.initial_state()

    for record, assigned_address in zip(records, shuffled, strict=True):
        _record_id, key, content, original_address = record
        assert assigned_address != original_address
        state, _ = controller.condense(state, cue=content, address=assigned_address)
        state, _ = controller.condense(
            state,
            cue=f"remember {key} field memory",
            address=assigned_address,
        )

    state = controller.evolve(state, steps=128)
    recalls = [
        controller.recall(
            state,
            f"please recall the {record[1]}",
            candidate_addresses=manifest,
        )
        for record in records
    ]
    assert [recall.address for recall in recalls] == shuffled
    assert all(
        recall.address != record[3]
        for recall, record in zip(recalls, records, strict=True)
    )
    assert min(recall.signal for recall in recalls) >= controller.config.minimum_recall_signal
    assert min(recall.selection_margin for recall in recalls) >= controller.config.minimum_recall_margin


def test_address_targeted_inhibition_preserves_other_memory() -> None:
    controller = MnemicCondensationController(
        MnemicCondensationConfig(cue_dimensions=512, slow_retention=0.99999)
    )
    first, second = _records(2)
    manifest = [first[3], second[3]]
    state = controller.initial_state()
    state, _ = controller.condense(state, cue=first[2], address=first[3])
    state, _ = controller.condense(state, cue=second[2], address=second[3])

    assert controller.recall(
        state,
        second[2],
        candidate_addresses=manifest,
    ).address == second[3]

    inhibited = controller.inhibit(
        state,
        cue=first[2],
        address=first[3],
    )
    assert controller.recall(
        inhibited,
        first[2],
        candidate_addresses=[first[3]],
    ).address is None
    assert controller.recall(
        inhibited,
        first[2],
        candidate_addresses=manifest,
    ).address != first[3]
    assert controller.recall(
        inhibited,
        second[2],
        candidate_addresses=manifest,
    ).address == second[3]
