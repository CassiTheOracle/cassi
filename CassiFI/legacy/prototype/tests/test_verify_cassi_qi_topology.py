"""Focused tests for the independent W4R verifier identity gate."""

from __future__ import annotations

import unittest

from verify_cassi_qi_topology import (
    ARTIFACT_DOMAIN,
    VerificationError,
    _hash,
    _verify_core_law_identity,
)


class CoreLawIdentityTests(unittest.TestCase):
    @staticmethod
    def _core() -> dict[str, object]:
        body: dict[str, object] = {
            "schema": "cassi.qi-flow-w4r-retention-core-law-identity.v1",
            "module": "cassi_qi_topology",
            "class": "QiTopologicalRetentionLaw",
            "transition": "cassi_qi_topology.QiTopologicalRetentionLaw.transition_w4r_topology",
            "reset": "transition_kind=retention_reset",
            "immutable_public_transition": True,
            "additional_state": False,
        }
        body["self_sha256"] = _hash(body, ARTIFACT_DOMAIN + ".core-law")
        return body

    def test_accepts_landed_class_qualified_transition(self) -> None:
        _verify_core_law_identity(self._core())

    def test_rejects_legacy_module_only_transition(self) -> None:
        core = self._core()
        core["transition"] = "cassi_qi_topology.transition_w4r_topology"
        with self.assertRaises(VerificationError):
            _verify_core_law_identity(core)

    def test_rejects_tampered_core_identity_hash(self) -> None:
        core = self._core()
        core["class"] = "OtherLaw"
        with self.assertRaises(VerificationError):
            _verify_core_law_identity(core)


if __name__ == "__main__":
    unittest.main()
