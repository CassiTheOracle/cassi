#!/usr/bin/env python3
"""Focused regression for the complete universal-interpreter program."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))

from run_cassi_universal_interpreter_full_program import run  # noqa: E402
from verify_cassi_universal_interpreter_full_program import verify  # noqa: E402


class UniversalInterpreterFullProgramTests(unittest.TestCase):
    def test_twelve_steps_and_persistent_branches_verify(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cassi-universal-interpreter-full-test-") as directory:
            root = Path(directory) / "program"
            receipt = run(root)
            receipt_path = root / "full-program-receipt.json"
            verified = verify(root, receipt_path)

            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(verified["status"], "PASS")
            self.assertEqual(len(verified["verified_generations"]), 6)
            self.assertTrue(receipt["checks"]["step_06_correction_repairs_dependents_locally"])
            self.assertTrue(receipt["checks"]["step_09_relation_removal_is_selective"])
            self.assertTrue(receipt["checks"]["step_12_method_reuses_across_family_after_restart"])
            self.assertEqual(
                receipt["structured_lifecycle"]["step_12_method_transfer"]["fixed_arm"]["error"],
                8.0,
            )
            self.assertEqual(
                receipt["structured_lifecycle"]["step_12_method_transfer"]["acquired_arm"]["after_method_value"],
                9.0,
            )

            tampered = copy.deepcopy(receipt)
            tampered["structured_lifecycle"]["step_06_correction_and_repair"]["repaired_prediction"] = 999.0
            tampered_path = Path(directory) / "tampered-receipt.json"
            tampered_path.write_text(
                json.dumps(tampered, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            tampered_result = verify(root, tampered_path)
            self.assertEqual(tampered_result["status"], "FAIL")
            self.assertTrue(any("content_sha256" in error for error in tampered_result["errors"]))

            source = json.loads((root / "source-manifest.json").read_text(encoding="utf-8"))
            source["observations"]["thermal_gap"]["outcome"] = 10.0
            (root / "source-manifest.json").write_text(
                json.dumps(source, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            source_result = verify(root, receipt_path)
            self.assertEqual(source_result["status"], "FAIL")
            self.assertTrue(any("source.source_revisions.thermal" in error for error in source_result["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
