from __future__ import annotations

import math

import pytest

from cassi_particle_program import (
    PARTICLE_PROGRAM_SCHEMA,
    ParticleProgramError,
    deterministic_particle_program,
    normalize_program,
    program_digest,
)


def _context() -> dict[str, object]:
    return {
        "cursor": [2.0, 3.0, 4.0],
        "selection": {
            "type": "sphere",
            "center": [0.0, 0.0, 0.0],
            "radius": 10.0,
        },
        "particle_count": 96,
        "constraints": {
            "maximum_particles": 96,
            "maximum_displacement": 50.0,
            "maximum_speed": 4.0,
        },
    }


def _program(target: dict[str, object]) -> dict[str, object]:
    return {
        "schema": PARTICLE_PROGRAM_SCHEMA,
        "operation": "arrange",
        "selection": {"type": "all"},
        "target": target,
        "motion": {"type": "exact", "velocity_policy": "zero"},
        "constraints": {
            "maximum_particles": 96,
            "maximum_displacement": 50.0,
            "maximum_speed": 4.0,
        },
        "source": {"kind": "explicit"},
        "request_id": "fixture-1",
    }

def test_godot_adoption_fixture_has_cross_runtime_digest() -> None:
    program = _program(
        {
            "type": "ring",
            "center": [0.0, 0.0, 0.0],
            "normal": [0.0, 1.0, 0.0],
            "radius": 2.0,
            "phase": 0.0,
        }
    )
    program["selection"] = {
        "type": "sphere",
        "center": [0.0, 0.0, 0.0],
        "radius": 100.0,
    }
    program["constraints"] = {
        "maximum_particles": 96,
        "maximum_displacement": 100.0,
        "maximum_speed": 10.0,
    }
    program["request_id"] = "pwa-ring-0001"

    assert program_digest(program) == (
        "858acbfe6298fd3526fdb7785280d23ec1f22fe6a402adcb1a52eb3b6a8c6010"
    )


def test_compiles_adoption_ring_request_deterministically() -> None:
    message = "Arrange the selected particles into a ring around the orange cursor, radius 7"
    first = deterministic_particle_program(message, _context(), request_id="turn-1")
    second = deterministic_particle_program(message, _context(), request_id="turn-1")

    assert first == second
    assert first["selection"] == _context()["selection"]
    assert first["target"] == {
        "type": "ring",
        "center": [2.0, 3.0, 4.0],
        "normal": [0.0, 1.0, 0.0],
        "radius": 7.0,
        "phase": 0.0,
    }
    assert first["motion"] == {"type": "exact", "velocity_policy": "zero"}
    assert program_digest(first) == program_digest(second)


@pytest.mark.parametrize(
    ("message", "target_type"),
    [
        ("make a line length 9 direction 0,0,1", "line"),
        ("make a sphere radius 3", "sphere"),
        ("make a grid spacing 2", "grid"),
        ("make a helix radius 2 pitch 4 turns 5", "helix"),
        ("make a double helix radius 2 pitch 4 turns 5", "double_helix"),
        ("translate by 1,-2,3", "translate"),
        ("scale factor 1.5", "scale"),
        ("rotate angle -90 axis 0,0,1", "rotate"),
    ],
)
def test_compiles_every_registered_procedural_target(
    message: str, target_type: str
) -> None:
    program = deterministic_particle_program(message, _context(), request_id="turn-2")
    assert program["target"]["type"] == target_type
    if target_type == "rotate":
        assert program["target"]["angle_radians"] == pytest.approx(-math.pi / 2.0)


def test_point_cloud_is_sorted_with_duplicate_order_stable() -> None:
    normalized = normalize_program(
        _program(
            {
                "type": "point_cloud",
                "points": [[2, 0, 0], [1, 0, 0], [1.0, 0.0, 0.0]],
            }
        )
    )
    assert normalized["target"]["points"] == [
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
    ]


def test_compiles_bounded_point_cloud_json() -> None:
    program = deterministic_particle_program(
        "point cloud points: [[1,2,3],[0,0,0]]",
        _context(),
        request_id="turn-3",
    )
    assert program["target"] == {
        "type": "point_cloud",
        "points": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"extra": True}),
        lambda value: value.update({"request_id": "bad request"}),
        lambda value: value["target"].update({"radius": float("nan")}),
        lambda value: value["constraints"].update({"maximum_particles": 0}),
        lambda value: value["motion"].update({"velocity_policy": "invent"}),
    ],
)
def test_rejects_malformed_nonfinite_and_out_of_policy_programs(mutation) -> None:
    value = _program(
        {
            "type": "ring",
            "center": [0.0, 0.0, 0.0],
            "normal": [0.0, 1.0, 0.0],
            "radius": 4.0,
            "phase": 0.0,
        }
    )
    mutation(value)
    with pytest.raises(ParticleProgramError):
        normalize_program(value)


def test_unknown_language_request_returns_clarification_error() -> None:
    with pytest.raises(ParticleProgramError, match="name one target"):
        deterministic_particle_program(
            "please make it beautiful", _context(), request_id="turn-4"
        )
