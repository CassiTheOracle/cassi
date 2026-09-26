from __future__ import annotations

from pathlib import Path
import sys

import pytest

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

from programs.model import draft_learning
from programs.python.records import digest_value


def _trained_policy() -> dict[str, object]:
    policy = draft_learning.initial_policy(
        model_program_id="qwen-test",
        source_sha256="a" * 64,
        max_horizon=3,
        max_context_width=1,
        max_methods=1,
        min_confidence=0.5,
    )
    policy = draft_learning.record_target_sequence(policy, [7], [1, 2, 1, 2])
    policy["methods"][0]["horizon"] = 3  # type: ignore[index]
    return policy


def test_deterministic_draft_exports_its_actual_point_mass_q() -> None:
    proposal = draft_learning.propose_draft(_trained_policy(), [7], max_tokens=3)

    assert proposal["draft_tokens"] == [1, 2, 1]
    assert proposal["proposal_q"] == [
        [{"token": token, "probability": 1.0}] for token in proposal["draft_tokens"]
    ]
    frame = draft_learning.speculation_frame(proposal)
    assert frame["proposal_q"] == proposal["proposal_q"]


def test_frame_rejects_empirical_frequency_misrepresented_as_deterministic_q() -> None:
    proposal = draft_learning.propose_draft(_trained_policy(), [7], max_tokens=1)
    proposal["proposal_q"] = [[
        {"token": proposal["draft_tokens"][0], "probability": 0.5},
        {"token": 99, "probability": 0.5},
    ]]
    proposal["proposal_sha256"] = digest_value(
        {key: value for key, value in proposal.items() if key != "proposal_sha256"}
    )

    with pytest.raises(draft_learning.DraftLearningError, match="unit mass"):
        draft_learning.speculation_frame(proposal)
