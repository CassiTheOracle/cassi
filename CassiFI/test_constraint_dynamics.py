from __future__ import annotations

import base64

import numpy as np
import pytest

from cassi_constraint_dynamics import (
    PROFILE_LAYOUT,
    SCHEMA,
    STEP_SCHEMA,
    ExcitableConstraintController,
    ExcitableConstraintError,
    ExcitableConstraintProfile,
    ExcitableConstraintState,
)

_SAFE_INTEGER = 2**53 - 1


def controller(size: int = 4, scale: int = 1024, max_ticks: int = 100_000) -> ExcitableConstraintController:
    return ExcitableConstraintController(
        ExcitableConstraintProfile(size=size, scale=scale, max_ticks=max_ticks)
    )


def lanes(state: ExcitableConstraintState, size: int) -> dict[str, np.ndarray]:
    field = state.field
    return {
        "excitation": field[0:size],
        "recovery": field[size : 2 * size],
        "trace": field[2 * size : 3 * size],
        "previous": field[3 * size : 4 * size],
        "header": field[4 * size :],
    }


def mutate(state: ExcitableConstraintState, index: int, value: float) -> ExcitableConstraintState:
    field = state.field
    field[index] = value
    return ExcitableConstraintState(field, state.profile_sha256)


def reference_ticks(
    excitation: list[int],
    recovery: list[int],
    trace: list[int],
    previous: list[int],
    drive: list[int],
    scale: int,
    ticks: int,
) -> tuple[list[int], list[int], list[int], list[int]]:
    """The documented recurrence, written independently of the numpy path."""

    def trunc(numer: int, denom: int) -> int:
        return numer // denom if numer >= 0 else -((-numer) // denom)

    def clamp(value: int) -> int:
        return min(scale, max(0, value))

    size = len(excitation)
    for _ in range(ticks):
        next_excitation = []
        next_recovery = []
        next_trace = []
        for site in range(size):
            flux = trunc(
                previous[(site - 1) % size] + previous[(site + 1) % size] - 2 * previous[site],
                16,
            )
            next_excitation.append(
                clamp(
                    excitation[site]
                    + flux
                    - trunc(excitation[site], 64)
                    - trunc(recovery[site], 4)
                    + drive[site]
                )
            )
            next_recovery.append(
                clamp(recovery[site] + trunc(previous[site], 16) - 1 - trunc(recovery[site], 32))
            )
            next_trace.append(
                clamp(trace[site] + trunc(previous[site], 4) - 1 - trunc(trace[site], 16))
            )
        previous, excitation, recovery, trace = excitation, next_excitation, next_recovery, next_trace
    return excitation, recovery, trace, previous


def chain(
    field: ExcitableConstraintController, steps: int = 40
) -> tuple[list[int | None], list[str]]:
    state = field.initial()
    literals: list[int | None] = []
    digests: list[str] = []
    for step in range(steps):
        variables = 1 + step % 5
        positive = [(step * 7 + index * 3) % 5 for index in range(variables)]
        negative = [(step * 5 + index) % 4 for index in range(variables)]
        eligible = [1 if (step + index) % 3 else 0 for index in range(variables)]
        state, literal, _ = field.advance(
            state, positive=positive, negative=negative, eligible=eligible
        )
        if step % 7 == 3:
            state = field.intervene(
                state,
                variable=1 + step % variables,
                excitation=(step * 37) % field.profile.scale,
            )
        literals.append(literal)
        digests.append(field.state_sha256(state))
    return literals, digests


def test_two_identical_runs_replay_to_identical_digests_and_selections() -> None:
    first_literals, first_digests = chain(controller())
    second_literals, second_digests = chain(controller())

    assert first_literals == second_literals
    assert first_digests == second_digests
    assert len(set(first_digests)) > 20
    assert any(literal is not None for literal in first_literals)


def test_selection_is_confined_to_eligible_variables_and_absent_without_any() -> None:
    field = controller()
    state = field.initial()

    _, literal, receipt = field.advance(
        state, positive=[9, 1, 9, 1], negative=[0, 0, 0, 0], eligible=[0, 1, 0, 0]
    )
    assert literal == 2
    assert receipt["selected_variable"] == 2
    assert receipt["selected_literal"] == 2
    assert receipt["schema"] == STEP_SCHEMA

    state = field.initial()
    seen = set()
    for _ in range(4):
        state, literal, receipt = field.advance(
            state, positive=[1, 4, 9, 2], negative=[0, 1, 0, 0], eligible=[0, 1, 0, 1]
        )
        seen.add(receipt["selected_variable"])
    assert seen <= {2, 4}

    state = field.initial()
    digest_before = field.state_sha256(state)
    successor, literal, receipt = field.advance(
        state, positive=[1, 1, 1, 1], negative=[0, 0, 0, 0], eligible=[0, 0, 0, 0]
    )
    assert literal is None
    assert receipt == {
        "schema": STEP_SCHEMA,
        "selected_literal": None,
        "selected_variable": None,
        "score": 0,
        "ticks": 4,
        "work": {"ticks": 4, "local_ops": 4 * 4 * 4},
    }
    # A tick still ran: the field moved even though no decision was available.
    assert field.state_sha256(successor) != digest_before


def test_signed_literal_follows_the_activity_polarity() -> None:
    field = controller(size=3, scale=1024)

    _, literal, receipt = field.advance(
        field.initial(), positive=[0, 0, 2], negative=[1, 0, 5], eligible=[1, 1, 1]
    )
    assert (literal, receipt["selected_variable"]) == (-3, 3)

    _, literal, receipt = field.advance(
        field.initial(), positive=[4, 0, 0], negative=[1, 0, 0], eligible=[1, 1, 1]
    )
    assert (literal, receipt["selected_variable"]) == (1, 1)

    _, literal, receipt = field.advance(
        field.initial(), positive=[0, 3, 0], negative=[0, 3, 0], eligible=[1, 1, 1]
    )
    assert (literal, receipt["selected_variable"]) == (-2, 2)


def test_intervention_flips_an_equal_activity_selection_and_changes_its_score() -> None:
    field = controller(size=4)
    state = field.initial()
    positive = [0, 1, 0, 1]
    negative = [0, 0, 0, 0]
    eligible = [1, 1, 1, 1]

    _, plain_literal, plain_receipt = field.advance(
        state, positive=positive, negative=negative, eligible=eligible
    )
    assert plain_literal == 2

    intervened = field.intervene(state, variable=4, excitation=field.profile.scale)
    assert field.state_sha256(intervened) != field.state_sha256(state)
    _, flipped_literal, flipped_receipt = field.advance(
        intervened, positive=positive, negative=negative, eligible=eligible
    )

    assert flipped_literal == 4
    assert flipped_receipt["selected_variable"] == 4
    # Equal solver activity, so the whole receipt difference is field-owned.
    assert flipped_receipt["score"] > plain_receipt["score"]
    assert flipped_receipt["score"] - plain_receipt["score"] == 394


def test_intervention_writes_only_one_excitation_lane_and_is_exactly_bounded() -> None:
    field = controller(size=4)
    state = field.initial()
    intervened = field.intervene(state, variable=6, excitation=777)

    before = state.field
    after = intervened.field
    changed = np.flatnonzero(after - before)
    assert changed.tolist() == [(6 - 1) % 4, 4 * 4 + 5]
    assert after[(6 - 1) % 4] == 777
    assert after[4 * 4 + 5] == 1
    field.validate(intervened)
    assert field.state_sha256(intervened) == field.state_sha256(
        field.intervene(state, variable=6, excitation=777)
    )


def test_selected_site_is_consumed_and_left_refractory() -> None:
    field = controller(size=4)
    state = field.initial()
    successor, literal, _ = field.advance(
        state, positive=[0, 0, 0, 0], negative=[0, 0, 0, 0], eligible=[1, 1, 1, 1]
    )
    assert literal == -1
    assert successor.field[:4].tolist() == [0, 0, 0, 0]
    assert successor.field[4:8].tolist() == [1024, 0, 0, 0]

    following, literal, _ = field.advance(
        successor, positive=[0, 0, 0, 0], negative=[0, 0, 0, 0], eligible=[1, 1, 1, 1]
    )
    # Site 1 is still refractory, so an equal-activity decision walks to
    # variable 2, whose site is then consumed at full strength.
    assert literal == -2
    assert following.field[4:8].tolist() == [899, 1024, 0, 0]


def test_equal_activity_decisions_walk_across_the_ring() -> None:
    field = controller(size=4)
    state = field.initial()
    positive = [1, 0, 1, 0]
    negative = [0, 1, 0, 1]
    selected: list[int | None] = []
    for _ in range(6):
        state, literal, _ = field.advance(
            state, positive=positive, negative=negative, eligible=[1, 1, 1, 1]
        )
        selected.append(literal)

    # Every variable carries the same activity, so the whole sequence is the
    # controller's own field: consumption plus refractoriness keeps moving it.
    assert len(set(selected[:6])) >= 3
    assert selected[0] != selected[1]
    assert all(literal is not None and abs(literal) <= 4 for literal in selected)


def test_relaxation_matches_the_documented_fixed_point_recurrence() -> None:
    field = controller(size=4)
    state = field.intervene(field.initial(), variable=1, excitation=1000)
    successor, literal, receipt = field.advance(
        state, positive=[1, 1, 1, 1], negative=[0, 0, 0, 0], eligible=[0, 0, 0, 0]
    )
    assert literal is None
    assert receipt["work"] == {"ticks": 4, "local_ops": 4 * 4 * 4}

    expected = reference_ticks(
        excitation=[1000, 0, 0, 0],
        recovery=[0, 0, 0, 0],
        trace=[0, 0, 0, 0],
        previous=[0, 0, 0, 0],
        drive=[8, 8, 8, 8],
        scale=field.profile.scale,
        ticks=4,
    )
    lanes_after = lanes(successor, 4)
    for lane, want in zip(
        (lanes_after["excitation"], lanes_after["recovery"], lanes_after["trace"], lanes_after["previous"]),
        expected,
    ):
        assert lane.tolist() == want
    # The delay lane holds the excitation of the previous tick, not the new one.
    assert lanes_after["previous"].tolist() != lanes_after["excitation"].tolist()
    assert lanes_after["previous"][0] > lanes_after["excitation"][0]


def test_long_horizon_ticks_stay_exact_integer_and_bounded() -> None:
    field = controller(size=8, max_ticks=100_000)
    state = field.initial()
    positive = [1, 0, 2, 3, 0, 1, 4, 2]
    negative = [0, 1, 0, 0, 2, 1, 0, 3]
    for _ in range(1300):
        state, _, _ = field.advance(
            state, positive=positive, negative=negative, eligible=[1] * 8
        )

    field.validate(state)
    raw = state.field
    assert raw[4 * 8 + 3] == 4 * 1300
    assert 4 * 1300 > 5000
    assert np.equal(raw, np.floor(raw)).all()
    assert np.isfinite(raw).all()
    assert raw[: 4 * 8].min() >= 0
    assert raw[: 4 * 8].max() <= field.profile.scale
    assert raw[4 * 8 + 7] == 0
    assert field.state_sha256(state) == field.state_sha256(
        ExcitableConstraintState(raw, field.profile.fingerprint)
    )


def test_tick_budget_is_a_bounded_terminal_lifetime() -> None:
    field = controller(size=4, max_ticks=8)
    state = field.initial()
    arguments = {"positive": [1, 1, 1, 1], "negative": [0, 0, 0, 0], "eligible": [1, 1, 1, 1]}
    for _ in range(2):
        state, literal, receipt = field.advance(state, **arguments)
        assert receipt["work"]["ticks"] == 4
        assert literal is not None
    assert state.field[4 * 4 + 3] == 8

    frozen, literal, receipt = field.advance(state, **arguments)
    assert receipt["work"] == {"ticks": 0, "local_ops": 0}
    assert receipt["ticks"] == 8
    assert literal is not None
    assert frozen.field[4 * 4 + 3] == 8
    field.validate(frozen)
    # No tick ran, so only the consumed decision and the counters moved.
    site = receipt["selected_variable"] - 1
    untouched = [index for index in range(4 * 4) if index not in (site, site + 4)]
    assert frozen.field[untouched].tolist() == state.field[untouched].tolist()
    assert frozen.field[site] == 0
    assert frozen.field[site + 4] == field.profile.scale

    partial = controller(size=4, max_ticks=6)
    state = partial.initial()
    state, _, receipt = partial.advance(state, **arguments)
    assert receipt["work"]["ticks"] == 4
    state, _, receipt = partial.advance(state, **arguments)
    assert receipt["work"]["ticks"] == 2
    state, _, receipt = partial.advance(state, **arguments)
    assert receipt["work"]["ticks"] == 0
    assert state.field[4 * 4 + 3] == 6


def test_header_lanes_record_magic_geometry_and_counters() -> None:
    field = controller(size=4)
    state = field.initial()
    size = 4
    assert state.field[4 * size :].tolist() == [0xEC51, 4, 1024, 0, 0, 0, 0, 0]

    state, _, _ = field.advance(
        state, positive=[1, 0, 1, 0], negative=[0, 1, 0, 1], eligible=[1, 1, 1, 1]
    )
    assert state.field[4 * size :].tolist() == [0xEC51, 4, 1024, 4, 1, 0, 1, 0]

    state = field.intervene(state, variable=2, excitation=64)
    assert state.field[4 * size :].tolist() == [0xEC51, 4, 1024, 4, 1, 1, 1, 0]
    assert state.field[1] == 64


def test_descriptor_round_trip_preserves_the_field_and_its_continuation() -> None:
    field = controller(size=3, scale=512)
    state = field.initial()
    for _ in range(5):
        state, _, _ = field.advance(
            state, positive=[2, 1, 0], negative=[0, 0, 3], eligible=[1, 1, 1]
        )

    descriptor = field.descriptor(state)
    assert descriptor["schema"] == SCHEMA
    assert descriptor["layout"] == PROFILE_LAYOUT
    assert descriptor["profile"] == {"size": 3, "scale": 512, "max_ticks": 100_000}
    assert descriptor["profile_sha256"] == field.profile.fingerprint
    assert descriptor["state_sha256"] == field.state_sha256(state)

    restored, restored_state = ExcitableConstraintController.from_descriptor(descriptor)
    assert restored.profile == field.profile
    assert restored_state.field.tolist() == state.field.tolist()
    assert restored.state_sha256(restored_state) == field.state_sha256(state)

    for _ in range(4):
        state, original_literal, _ = field.advance(
            state, positive=[2, 1, 0], negative=[0, 0, 3], eligible=[1, 1, 1]
        )
        restored_state, restored_literal, _ = restored.advance(
            restored_state, positive=[2, 1, 0], negative=[0, 0, 3], eligible=[1, 1, 1]
        )
        assert restored_literal == original_literal
    assert restored.state_sha256(restored_state) == field.state_sha256(state)


def test_descriptor_tampering_is_rejected() -> None:
    field = controller(size=3)
    state = field.initial()
    state, _, _ = field.advance(
        state, positive=[1, 1, 1], negative=[0, 0, 0], eligible=[1, 1, 1]
    )
    descriptor = field.descriptor(state)

    def tampered(**changes: object) -> dict:
        value = dict(descriptor)
        value.update(changes)
        return value

    raw = base64.b64decode(descriptor["field_b64"])
    flipped = bytearray(raw)
    flipped[0] ^= 0x01
    # A flipped float64 byte is no longer an exact in-range lane value, so the
    # codec fails closed before it can even compare the digest.
    with pytest.raises(ExcitableConstraintError):
        ExcitableConstraintController.from_descriptor(
            tampered(field_b64=base64.b64encode(bytes(flipped)).decode("ascii"))
        )
    altered = np.frombuffer(raw, dtype=np.float64).copy()
    altered[0] = altered[0] + 1
    with pytest.raises(ExcitableConstraintError, match="state digest mismatch"):
        ExcitableConstraintController.from_descriptor(
            tampered(field_b64=base64.b64encode(altered).decode("ascii"))
        )
    with pytest.raises(ExcitableConstraintError, match="encoding is invalid"):
        ExcitableConstraintController.from_descriptor(tampered(field_b64="not base64!"))
    with pytest.raises(ExcitableConstraintError, match="wrong byte length"):
        ExcitableConstraintController.from_descriptor(
            tampered(field_b64=base64.b64encode(np.zeros(3, dtype=np.float64)).decode("ascii"))
        )
    with pytest.raises(ExcitableConstraintError, match="state digest mismatch"):
        ExcitableConstraintController.from_descriptor(tampered(state_sha256="0" * 64))
    with pytest.raises(ExcitableConstraintError, match="profile digest mismatch"):
        ExcitableConstraintController.from_descriptor(tampered(profile_sha256="0" * 64))
    with pytest.raises(ExcitableConstraintError, match="profile digest mismatch"):
        ExcitableConstraintController.from_descriptor(
            tampered(profile={"size": 3, "scale": 512, "max_ticks": 100_000})
        )
    with pytest.raises(ExcitableConstraintError, match="unsupported"):
        ExcitableConstraintController.from_descriptor(tampered(schema="cassifi.excitable.v9"))
    with pytest.raises(ExcitableConstraintError, match="descriptor keys"):
        ExcitableConstraintController.from_descriptor(tampered(extra=1))
    missing = dict(descriptor)
    del missing["profile"]
    with pytest.raises(ExcitableConstraintError, match="descriptor keys"):
        ExcitableConstraintController.from_descriptor(missing)


def test_malformed_activity_and_eligibility_inputs_fail_closed() -> None:
    field = controller(size=3)
    state = field.initial()

    with pytest.raises(ExcitableConstraintError, match="equal length"):
        field.advance(state, positive=[1, 1, 1], negative=[0, 0], eligible=[1, 1, 1])
    with pytest.raises(ExcitableConstraintError, match="equal length"):
        field.advance(state, positive=[1, 1, 1], negative=[0, 0, 0], eligible=[1, 1])
    with pytest.raises(ExcitableConstraintError, match="cannot be negative"):
        field.advance(state, positive=[1, -1, 1], negative=[0, 0, 0], eligible=[1, 1, 1])
    with pytest.raises(ExcitableConstraintError, match="cannot be negative"):
        field.advance(state, positive=[1, 1, 1], negative=[0, -2, 0], eligible=[1, 1, 1])
    with pytest.raises(ExcitableConstraintError, match="exact integers"):
        field.advance(state, positive=[1.0, 1, 1], negative=[0, 0, 0], eligible=[1, 1, 1])
    with pytest.raises(ExcitableConstraintError, match="exact integers"):
        field.advance(state, positive=[True, 1, 1], negative=[0, 0, 0], eligible=[1, 1, 1])
    with pytest.raises(ExcitableConstraintError, match="ordered integer sequence"):
        field.advance(state, positive="111", negative=[0, 0, 0], eligible=[1, 1, 1])
    with pytest.raises(ExcitableConstraintError, match="ordered integer sequence"):
        field.advance(
            state,
            positive=np.array([[1, 1, 1]], dtype=np.int64),
            negative=[0, 0, 0],
            eligible=[1, 1, 1],
        )
    with pytest.raises(ExcitableConstraintError, match="ordered integer sequence"):
        field.advance(
            state,
            positive=[1, 1, 1],
            negative=[0, 0, 0],
            eligible=np.ones((1, 3), dtype=bool),
        )
    with pytest.raises(ExcitableConstraintError, match="exact integers"):
        field.advance(state, positive=[1, 1, 1], negative=[0, 0, 0], eligible=[1, None, 1])
    with pytest.raises(ExcitableConstraintError, match="exact float64 integer range"):
        field.advance(
            state, positive=[_SAFE_INTEGER + 1, 0, 0], negative=[0, 0, 0], eligible=[1, 1, 1]
        )
    with pytest.raises(ExcitableConstraintError, match="ExcitableConstraintState"):
        field.advance(None, positive=[1], negative=[0], eligible=[1])


def test_numpy_activity_and_eligibility_sequences_are_accepted() -> None:
    field = controller(size=3)
    state = field.initial()
    successor, literal, receipt = field.advance(
        state,
        positive=np.array([0, 1, 0], dtype=np.int64),
        negative=np.array([0, 0, 0], dtype=np.int64),
        eligible=np.array([False, True, False]),
    )
    assert (literal, receipt["selected_variable"]) == (2, 2)
    field.validate(successor)

    _, literal, receipt = field.advance(
        state, positive=[], negative=[], eligible=[]
    )
    assert literal is None
    # The ring still relaxes: four ticks over four lanes at every site.
    assert receipt["work"] == {"ticks": 4, "local_ops": 4 * 3 * 4}


def test_malformed_interventions_fail_closed() -> None:
    field = controller(size=4, scale=1024)
    state = field.initial()

    for variable in (0, -1, True, 1.0, _SAFE_INTEGER + 1):
        with pytest.raises(ExcitableConstraintError, match="variable must be an exact bounded integer"):
            field.intervene(state, variable=variable, excitation=1)
    for excitation in (-1, True, 2.5, 1025, _SAFE_INTEGER + 1):
        with pytest.raises(ExcitableConstraintError):
            field.intervene(state, variable=1, excitation=excitation)

    for variable in (1, 4, 5, 12):
        candidate = field.intervene(state, variable=variable, excitation=1024)
        assert candidate.field[(variable - 1) % 4] == 1024
        field.validate(candidate)

    wrapped = field.intervene(state, variable=_SAFE_INTEGER, excitation=0)
    assert wrapped.field[(_SAFE_INTEGER - 1) % 4] == 0
    field.validate(wrapped)


def test_malformed_states_fail_closed() -> None:
    field = controller(size=4, scale=1024)
    state = field.initial()
    size = 4

    with pytest.raises(ExcitableConstraintError, match="one-dimensional float64"):
        ExcitableConstraintState(np.zeros(4 * size + 8, dtype=np.int64), field.profile.fingerprint)
    with pytest.raises(ExcitableConstraintError, match="one-dimensional float64"):
        ExcitableConstraintState(
            np.zeros((1, 4 * size + 8), dtype=np.float64), field.profile.fingerprint
        )
    with pytest.raises(ExcitableConstraintError, match="one-dimensional float64"):
        ExcitableConstraintState(
            np.zeros((4 * size + 8, 1), dtype=np.float64), field.profile.fingerprint
        )
    with pytest.raises(ExcitableConstraintError, match="profile fingerprint"):
        ExcitableConstraintState(np.zeros(4 * size + 8, dtype=np.float64), "short")

    with pytest.raises(ExcitableConstraintError, match="invalid shape"):
        field.validate(
            ExcitableConstraintState(
                np.zeros(4 * size + 7, dtype=np.float64), field.profile.fingerprint
            )
        )
    with pytest.raises(ExcitableConstraintError, match="finite exact integers"):
        field.validate(mutate(state, 0, 0.5))
    with pytest.raises(ExcitableConstraintError, match="exceeds exact float64 integer range"):
        field.validate(mutate(state, 0, float(_SAFE_INTEGER + 1)))
    with pytest.raises(ExcitableConstraintError, match="outside the fixed-point range"):
        field.validate(mutate(state, 0, 1025))
    with pytest.raises(ExcitableConstraintError, match="outside the fixed-point range"):
        field.validate(mutate(state, 2 * size, -1))
    with pytest.raises(ExcitableConstraintError, match="magic is invalid"):
        field.validate(mutate(state, 4 * size, 0))
    with pytest.raises(ExcitableConstraintError, match="site count disagrees"):
        field.validate(mutate(state, 4 * size + 1, 5))
    with pytest.raises(ExcitableConstraintError, match="scale disagrees"):
        field.validate(mutate(state, 4 * size + 2, 512))
    with pytest.raises(ExcitableConstraintError, match="padding must be zero"):
        field.validate(mutate(state, 4 * size + 7, 1))
    with pytest.raises(ExcitableConstraintError, match="counters cannot be negative"):
        field.validate(mutate(state, 4 * size + 4, -1))
    with pytest.raises(ExcitableConstraintError, match="tick counter exceeds"):
        field.validate(mutate(state, 4 * size + 3, 100_001))

    other = controller(size=4, scale=512).initial()
    with pytest.raises(ExcitableConstraintError, match="different excitable-constraint profile"):
        field.validate(other)
    with pytest.raises(ExcitableConstraintError, match="ExcitableConstraintState"):
        field.validate("state")

    # The field handed to a caller is a copy and the stored block is read-only.
    copy = state.field
    copy[0] = 9
    assert field.state_sha256(state) != field.state_sha256(mutate(state, 0, 9))
    assert not state._field.flags.writeable


def test_profile_bounds_and_fingerprint_are_strict() -> None:
    for size in (0, -1, True, 1.0, _SAFE_INTEGER + 1):
        with pytest.raises(ExcitableConstraintError, match="size"):
            ExcitableConstraintProfile(size=size)
    for scale in (7, 0, True, 8.0, _SAFE_INTEGER + 1):
        with pytest.raises(ExcitableConstraintError, match="scale"):
            ExcitableConstraintProfile(size=4, scale=scale)
    for max_ticks in (0, -5, False, 10.0, _SAFE_INTEGER + 1):
        with pytest.raises(ExcitableConstraintError, match="max_ticks"):
            ExcitableConstraintProfile(size=4, max_ticks=max_ticks)
    with pytest.raises(ExcitableConstraintError, match="ExcitableConstraintProfile"):
        ExcitableConstraintController({"size": 4})
    with pytest.raises(ExcitableConstraintError, match="exact address capacity"):
        ExcitableConstraintProfile(size=_SAFE_INTEGER // 4)

    base = ExcitableConstraintProfile(size=4)
    assert base.as_dict() == {"size": 4, "scale": 1024, "max_ticks": 100_000}
    assert len(base.fingerprint) == 64
    assert base.shape == (4 * 4 + 8,)
    assert base.lane_count == 24
    for other in (
        ExcitableConstraintProfile(size=5),
        ExcitableConstraintProfile(size=4, scale=512),
        ExcitableConstraintProfile(size=4, max_ticks=99),
    ):
        assert other.fingerprint != base.fingerprint


@pytest.mark.parametrize("counter_offset", (4, 6))
def test_raw_lane_counter_exhaustion_is_atomic(counter_offset: int) -> None:
    field = controller(size=2)
    raw = field.initial_lanes()
    coordinate = 4 * field.profile.size + counter_offset
    raw[coordinate] = _SAFE_INTEGER - 1
    activity = {"positive": [1, 1], "negative": [0, 0], "eligible": [1, 1]}

    field.advance_lanes(raw, **activity)
    assert int(raw[coordinate]) == _SAFE_INTEGER
    field.validate_lanes(raw)
    before = raw.tobytes()
    with pytest.raises(ExcitableConstraintError):
        field.advance_lanes(raw, **activity)
    assert raw.tobytes() == before
