"""Guest Python behavior across serializable continuations and capacity changes."""

import json

import pytest

from programs.python.compiler import compile_python
from programs.python.runtime import advance, initial_state


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            'namespace = {"old": 1}\n'
            'exec("def generated(n): return n * n + 1", namespace)\n'
            'exec("del old", namespace)\n'
            'print(namespace["generated"](11), "old" in namespace)\n',
            "122 False\n",
        ),
        (
            'namespace = {}\n'
            'try:\n'
            '    exec("saved = 7\\nraise ValueError(\'stop\')", namespace)\n'
            'except ValueError:\n'
            '    pass\n'
            'print(namespace["saved"])\n',
            "7\n",
        ),
    ],
    ids=["normal-return", "exception-unwind"],
)
def test_dynamic_namespace_survives_serialized_continuation(source, expected):
    state = initial_state(compile_python(source))
    for _ in range(500):
        state, status, _, output, _ = advance(state, None, 3)
        if status != "yield":
            assert status == "done", output
            assert state["stdout"] == expected
            return
        state = json.loads(json.dumps(state))
    pytest.fail("Dynamic execution did not complete within the work allowance")


def test_resource_growth_retries_only_the_unfinished_effect_request():
    source = (
        'first = request_effect("first")\n'
        'second = request_effect("second")\n'
        'print(first, second)\n'
    )
    state = initial_state(
        compile_python(source),
        capabilities=("effect-proposal",),
        limits={"max_operations": 1},
    )
    state, status, _, _, _ = advance(state, None, 64)
    assert status == "blocked"
    first_id = next(iter(state["operations"]))
    state, status, _, _, _ = advance(
        state, {"operation": "resume", "operation_id": first_id, "value": 17}, 64
    )
    assert status == "blocked"
    assert state["phase"] == "resource-paused"
    assert state["resource_wait"]["limit"] == "max_operations"
    assert state["resource_wait"]["required"] == 2
    assert list(state["operations"]) == [first_id]
    assert state["operations"][first_id]["phase"] == "settled"
    identity = state["identity"]
    paused_frames = state["frames"]

    state, status, _, _, _ = advance(
        json.loads(json.dumps(state)),
        {"operation": "increase-limits", "limits": {"max_operations": 2}},
        1,
    )
    assert status == "yield"
    assert state["identity"] == identity
    assert state["frames"] == paused_frames
    assert list(state["operations"]) == [first_id]
    state, status, _, _, _ = advance(json.loads(json.dumps(state)), None, 64)
    assert status == "blocked"
    assert len(state["operations"]) == 2
    second_id = next(key for key in state["operations"] if key != first_id)
    state, status, _, _, _ = advance(
        state, {"operation": "resume", "operation_id": second_id, "value": 29}, 64
    )
    assert status == "done"
    assert state["stdout"] == "17 29\n"
    assert [state["operations"][key]["phase"] for key in (first_id, second_id)] == [
        "settled", "settled"
    ]
