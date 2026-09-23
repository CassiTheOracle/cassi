from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cassi_field_qwen_workbench import CassiFieldWorkMemory
from cassi_teacher_field import TeacherFieldController


class TeacherFieldControllerTests(unittest.TestCase):
    def test_field_action_and_outcome_form_a_causal_chain(self) -> None:
        candidate = "result = 5 * value + 1"
        candidate_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        descriptors = [
            {
                "candidate_id": "identical_branch:canonical",
                "candidate_origin": "verified_pool",
                "candidate_sha256": candidate_sha256,
                "candidate_steps": 24,
                "improved": True,
                "status": "PASS",
                "task_id": "identical_branch",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            with CassiFieldWorkMemory(Path(directory)) as memory:
                controller = TeacherFieldController(memory, run_id="teacher-test")
                begin = controller.begin(
                    generation=0,
                    attempt=0,
                    previous_source_sha256="a" * 64,
                    candidate_descriptors=descriptors,
                    planned_edit_id="identical_branch:canonical",
                    thinking_max_tokens=128,
                    thinking_capability={
                        "answer_channel_viable": False,
                        "flag_effective": True,
                        "probe_max_tokens": 64,
                    },
                )
                self.assertEqual(begin["mode"], "field")
                self.assertEqual(begin["action"]["candidate_id"], descriptors[0]["candidate_id"])
                self.assertFalse(begin["action"]["thinking"]["enabled"])
                self.assertEqual(
                    begin["action"]["thinking"]["effort_code"],
                    "capability-floor-off",
                )
                self.assertEqual(
                    begin["action"]["predecessor_field_sha256"],
                    begin["observation_field_state_out_sha256"],
                )
                outcome = controller.observe_outcome(
                    begin,
                    status="PASS",
                    candidate_origin="verified_pool",
                    candidate_sha256=candidate_sha256,
                    task_id="identical_branch",
                    candidate_steps=24,
                    original_steps=40,
                    reasoning_chars=32,
                    completion_tokens=64,
                    thinking_requested=bool(begin["action"]["thinking"]["enabled"]),
                    thinking_effective=True,
                )
                self.assertEqual(outcome["status"], "observed")
                self.assertEqual(
                    outcome["field_state_in_sha256"], begin["field_state_out_sha256"]
                )
                self.assertNotEqual(
                    outcome["field_state_out_sha256"], outcome["field_state_in_sha256"]
                )

    def test_field_off_is_a_nonmutating_comparator(self) -> None:
        candidate = "result = 5 * value + 1"
        candidate_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        descriptors = [
            {
                "candidate_id": "identical_branch:canonical",
                "candidate_sha256": candidate_sha256,
                "candidate_steps": 24,
                "improved": True,
                "status": "PASS",
                "task_id": "identical_branch",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            with CassiFieldWorkMemory(Path(directory)) as memory:
                before = memory.regional_field_receipt()["field_state_sha256"]
                controller = TeacherFieldController(
                    memory, run_id="teacher-off-test", field_off=True
                )
                begin = controller.begin(
                    generation=0,
                    attempt=0,
                    previous_source_sha256="b" * 64,
                    candidate_descriptors=descriptors,
                    planned_edit_id=descriptors[0]["candidate_id"],
                )
                self.assertEqual(begin["mode"], "field-off")
                self.assertFalse(begin["action"]["thinking"]["enabled"])
                self.assertIsNone(begin["field_state_out_sha256"])
                outcome = controller.observe_outcome(
                    begin,
                    status="PASS",
                    candidate_origin="verified_pool",
                    candidate_sha256=candidate_sha256,
                    task_id="identical_branch",
                    candidate_steps=24,
                    original_steps=40,
                    reasoning_chars=0,
                    completion_tokens=32,
                    thinking_requested=False,
                    thinking_effective=False,
                )
                self.assertEqual(outcome["status"], "not-applicable")
                self.assertEqual(
                    memory.regional_field_receipt()["field_state_sha256"], before
                )


if __name__ == "__main__":
    unittest.main()
