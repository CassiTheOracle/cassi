from __future__ import annotations

import copy
import unittest

from cassi_skill_bundle import (
    SkillBundleError,
    build_skill_bundle,
    skill_contracts_from_bundle,
    verify_skill_bundle,
)


class SkillBundleTests(unittest.TestCase):
    def test_verified_math_python_curriculum_exports_and_round_trips(self) -> None:
        bundle = build_skill_bundle()
        verification = verify_skill_bundle(bundle)
        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification["skill_count"], 21)
        self.assertEqual(bundle["content_sha256"], verification["content_sha256"])
        self.assertTrue(all(skill["differential"]["passed"] for skill in bundle["skills"]))
        self.assertEqual(
            [skill["skill_id"] for skill in bundle["skills"] if "financial-math" in skill["domains"]],
            [f"FM{index}" for index in range(13)],
        )

    def test_bundle_exports_canonical_skill_contracts(self) -> None:
        bundle = build_skill_bundle()
        contracts = skill_contracts_from_bundle(bundle)
        self.assertEqual(len(contracts), bundle["skill_count"])
        self.assertEqual([skill.skill_id for skill in contracts], [row["skill_id"] for row in bundle["skills"]])
        for contract in contracts:
            self.assertEqual(contract.revision_id, bundle["content_sha256"])
            self.assertIn(f"skill-bundle:{bundle['content_sha256']}", contract.support_roots)
            self.assertEqual(contract.as_dict()["schema"], "cassi.market-skill.v1")
            self.assertEqual(len(contract.content_sha256), 64)

    def test_skill_source_mutation_is_rejected(self) -> None:
        bundle = build_skill_bundle()
        mutated = copy.deepcopy(bundle)
        mutated["skills"][0]["source"] = "result = 999"
        with self.assertRaises(SkillBundleError):
            verify_skill_bundle(mutated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
