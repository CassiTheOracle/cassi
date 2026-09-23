#!/usr/bin/env python3
"""Regression for the continuing-world universal-interpreter program."""

from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))

from run_cassi_universal_interpreter_program import run
from verify_cassi_universal_interpreter_program import verify


class UniversalInterpreterProgramTests(unittest.TestCase):
    def test_packet_correction_reaches_portable_field_meaning_and_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cassi-universal-interpreter-test-") as directory:
            root = Path(directory) / "program"
            receipt = run(root)
            receipt_path = Path(directory) / "program-receipt.json"
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            verified = verify(receipt_path, root)
            tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
            tampered["task"]["question"] = "tampered"
            tampered_path = Path(directory) / "tampered-receipt.json"
            tampered_path.write_text(
                json.dumps(tampered, ensure_ascii=False, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                verify(tampered_path, root)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(verified["status"], "PASS")
        self.assertEqual(receipt["task_handoff"]["premise_after"], 5.0)
        self.assertEqual(
            receipt["native_boundary"]["alternate_query"]["prediction"]["meaning"],
            receipt["native_boundary"]["query"]["prediction"]["meaning"],
        )
        self.assertTrue(receipt["checks"]["packet_resident_episode_reopened"])
        self.assertTrue(receipt["checks"]["packet_refinement_exercised"])
        self.assertTrue(receipt["checks"]["source_handoff_preserved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
