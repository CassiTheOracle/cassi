"""Verify held-out whole-utterance semantic frames and minimal pairs."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_discourse_language import CassiDiscourseEventCodec, select_discourse_frame
from cassi_field_language import CassiQiTextEngine
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_qi_field import QiFieldConfig, QiFieldController

CONFIG_PATH = CONFIG_DIR / "cassi-qi-corpus-language.json"
CHECKPOINT_PATH = ARTIFACT_DIR / "cassi-qi-discourse-language" / "field-state.pt"

CASES: tuple[tuple[str, str, dict[str, object]], ...] = (
    (
        "alias-left",
        "horizon means look left",
        {"route_id": "route.action-alias-binding", "commit": True, "action_id": "action.gaze-left"},
    ),
    (
        "alias-right",
        "horizon means look right",
        {"route_id": "route.action-alias-binding", "commit": True, "action_id": "action.gaze-right"},
    ),
    (
        "binding-red",
        "revise the name binding so Mira denotes red",
        {"route_id": "route.binding", "commit": True, "binding_reference": "reference.red", "subject_slot": "surface.alias-1"},
    ),
    (
        "binding-blue",
        "revise the name binding so Mira denotes blue",
        {"route_id": "route.binding", "commit": True, "binding_reference": "reference.blue", "subject_slot": "surface.alias-1"},
    ),
    (
        "prediction-left",
        "before acting predict what looking left will change",
        {"route_id": "route.prediction", "commit": False, "action_id": "action.gaze-left"},
    ),
    (
        "prediction-right",
        "before acting predict what looking right will change",
        {"route_id": "route.prediction", "commit": False, "action_id": "action.gaze-right"},
    ),
    (
        "ordering-forward",
        "which state came first or second",
        {"route_id": "route.ordering", "commit": False, "presentation": "forward"},
    ),
    (
        "ordering-reverse",
        "which state came second or first",
        {"route_id": "route.ordering", "commit": False, "presentation": "reverse"},
    ),
    (
        "long-binding-red",
        "using this exact request and no other operation revise the name binding so Mira denotes red",
        {"route_id": "route.binding", "commit": True, "binding_reference": "reference.red", "subject_slot": "surface.alias-1"},
    ),
    (
        "long-binding-blue",
        "using this exact request and no other operation revise the name binding so Mira denotes blue",
        {"route_id": "route.binding", "commit": True, "binding_reference": "reference.blue", "subject_slot": "surface.alias-1"},
    ),
    (
        "long-clarification",
        "please explain this request then turn right and left at the same time",
        {"route_id": "route.abstain", "commit": False, "clarification": "ambiguous_action"},
    ),
)

PAIR_FIELDS = (
    ("alias-left", "alias-right", "action_id"),
    ("binding-red", "binding-blue", "binding_reference"),
    ("prediction-left", "prediction-right", "action_id"),
    ("ordering-forward", "ordering-reverse", "presentation"),
    ("long-binding-red", "long-binding-blue", "binding_reference"),
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config = QiFieldConfig.from_dict(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    controller = QiFieldController(config)
    engine = CassiQiTextEngine(controller, checkpoint_path=CHECKPOINT_PATH)
    state = engine.initial_state(device="cpu")
    codec = CassiDiscourseEventCodec()
    memory_before = engine.law.memory_sha256(state)
    rows: dict[str, dict[str, object]] = {}
    failures: list[str] = []
    selected_rows: dict[str, dict[str, object]] = {}
    window_counts: dict[str, int] = {}

    for name, prompt, expected in CASES:
        try:
            decision = select_discourse_frame(controller, engine.law, codec, state, prompt)
        except Exception as error:
            failures.append(f"{name}: {type(error).__name__}: {error}")
            continue
        selected = decision.target.receipt_dict()
        mismatches = {
            key: {"expected": value, "selected": selected.get(key)}
            for key, value in expected.items()
            if selected.get(key) != value
        }
        if mismatches:
            failures.append(f"{name}: {mismatches}")
        if any(slot.margin <= 0.0 for slot in decision.slots):
            failures.append(f"{name}: nonpositive field-work margin")
        rows[name] = {
            "prompt": prompt,
            "selected": selected,
            "selected_window_index": decision.selected_window_index,
            "window_count": len(decision.cue_state_sha256),
            "minimum_slot_margin": min(slot.margin for slot in decision.slots),
        }
        selected_rows[name] = selected
        window_counts[name] = len(decision.cue_state_sha256)

    for left, right, field in PAIR_FIELDS:
        if left not in selected_rows or right not in selected_rows:
            continue
        left_value = selected_rows[left][field]
        right_value = selected_rows[right][field]
        if left_value == right_value:
            failures.append(f"{left}/{right}: minimal-pair field {field} did not change")

    for name in ("long-binding-red", "long-binding-blue", "long-clarification"):
        if window_counts.get(name, 0) <= 1:
            failures.append(f"{name}: utterance was not evaluated across sliding windows")

    memory_after = engine.law.memory_sha256(state)
    if memory_after != memory_before:
        failures.append("read-only frame evaluation changed field memory")

    receipt = {
        "schema": "cassi.qi-semantic-frame-verification.v1",
        "verdict": "PASS" if not failures else "FAIL",
        "case_count": len(CASES),
        "minimal_pair_count": len(PAIR_FIELDS),
        "checkpoint_path": str(CHECKPOINT_PATH),
        "checkpoint_sha256": file_sha256(CHECKPOINT_PATH),
        "memory_sha256": memory_before,
        "memory_unchanged": memory_before == memory_after,
        "failures": failures,
        "cases": rows,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
