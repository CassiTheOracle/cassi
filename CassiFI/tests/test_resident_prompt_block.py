"""The prompt block's continuation decision, at its boundaries.

One owner round may carry several consecutive prompt positions; the decision
that keeps a round open is this predicate, so its refusals are the contract a
generated token, a terminal task, a budget, or a gap in positions relies on.
"""
from __future__ import annotations

from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

from cassi_field_owner import _resident_prompt_block_continues  # noqa: E402

PROMPT_TOKENS = 8
_AUTO_STATE = object()


def _state(
    *,
    phase: str = "running",
    position: int = 3,
    token_index: int = 3,
    prompt_tokens: object = PROMPT_TOKENS,
) -> dict[str, object]:
    tokens = list(range(prompt_tokens)) if isinstance(prompt_tokens, int) else prompt_tokens
    return {
        "phase": phase,
        "resident_model": {"position": position, "token_index": token_index},
        "request": {"prompt_tokens": tokens},
    }


def _continues(
    *,
    block_positions: int,
    positions_done: int,
    completed_position: int = 2,
    next_position: int = 3,
    model_state: object = _AUTO_STATE,
) -> bool:
    return _resident_prompt_block_continues(
        block_positions=block_positions,
        positions_done=positions_done,
        completed_position=completed_position,
        next_position=next_position,
        model_state=(
            _state(position=next_position)
            if model_state is _AUTO_STATE
            else model_state
        ),
    )


def test_a_block_carries_the_round_into_the_next_prompt_position() -> None:
    assert _continues(block_positions=8, positions_done=0)


def test_a_single_position_round_never_continues() -> None:
    assert not _continues(block_positions=1, positions_done=0)


def test_the_position_budget_ends_the_round() -> None:
    assert _continues(block_positions=2, positions_done=0)
    assert not _continues(block_positions=2, positions_done=1)


def test_a_gap_in_positions_ends_the_round() -> None:
    assert not _continues(block_positions=8, positions_done=0, next_position=4)


def test_a_terminal_task_phase_ends_the_round() -> None:
    for phase in ("completed", "faulted", "cancelled"):
        assert not _continues(
            block_positions=8,
            positions_done=0,
            model_state=_state(phase=phase),
        )


def test_the_sampling_prompt_position_ends_the_round() -> None:
    """The last prompt position samples, so its head must close the round."""

    assert not _continues(
        block_positions=8,
        positions_done=0,
        model_state=_state(token_index=PROMPT_TOKENS),
    )
    assert _continues(
        block_positions=8,
        positions_done=0,
        model_state=_state(token_index=PROMPT_TOKENS - 1),
    )


def test_a_generated_position_ends_the_round() -> None:
    assert not _continues(
        block_positions=8,
        positions_done=0,
        model_state=_state(token_index=PROMPT_TOKENS + 2),
    )


def test_an_unreadable_task_state_ends_the_round() -> None:
    for state in (
        None,
        {},
        {"phase": "running", "resident_model": {"position": 3}},
        _state(prompt_tokens=[]),
        _state(prompt_tokens="prompt"),
        _state(token_index=True),
        _state(token_index=-1),
    ):
        assert not _continues(block_positions=8, positions_done=0, model_state=state)
