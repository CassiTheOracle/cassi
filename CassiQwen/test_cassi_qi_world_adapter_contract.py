"""Focused W13C pre-adapter brief and baseline-input contract tests."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from cassi_qi_bootstrap import canonical_json_bytes
from cassi_qi_world import WORLD_WIRE_REGISTRY_SHA256


ROOT = Path(__file__).resolve().parent
COSMOS = (ROOT / "../CassiCosmos").resolve()
BRIEF_PATH = ROOT / "CASSI-QI-WORLD-ADAPTER-BRIEF.json"
SCHEMA_REGISTRY_PATH = ROOT / "_diag" / "cassi-fi-schema-inputs" / "text-api.json"
PINNED_GODOT = (
    "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/"
    "GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe"
)
ADAPTER_TARGETS = (
    COSMOS / "scripts" / "cassi_qi_world_adapter.gd",
    COSMOS / "scenes" / "qi_world_adapter.tscn",
    COSMOS / "scenes" / "verify_qi_world_adapter.tscn",
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def brief_hash(brief: dict[str, object]) -> str:
    value = dict(brief)
    value["baseline_input_sha256"] = ""
    value["brief_sha256"] = ""
    return sha256(canonical_json_bytes(value))


def baseline_input_hash(brief: dict[str, object]) -> str:
    value = {
        "brief_id": brief["brief_id"],
        "brief_version": brief["brief_version"],
        "input_identities": brief["input_identities"],
        "adapter_config": brief["adapter_config"],
        "adapter_fixture": brief["adapter_fixture"],
        "godot_command": brief["battery_baseline"]["godot_command"],
        "scene_battery": brief["battery_baseline"]["scene_battery"],
    }
    return sha256(canonical_json_bytes(value))


class QiWorldAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))

    def test_brief_is_frozen_default_off_and_self_identifying(self) -> None:
        brief = self.brief
        self.assertEqual(brief["schema"], "cassi.qi-world-adapter-brief.v1")
        self.assertEqual(brief["brief_id"], "cassi-qi-world-adapter-w13c-v1")
        self.assertEqual(brief["owner"], "W13C")
        self.assertEqual(brief["pre_adapter_state"], "baseline-before-adapter-edit")
        self.assertEqual(brief["adapter_config"]["adapter_enabled"], False)
        self.assertEqual(brief["adapter_config"]["default_off"], True)
        self.assertEqual(brief["adapter_config"]["second_qi_field"], False)
        self.assertEqual(brief["baseline_input_sha256"], baseline_input_hash(brief))
        self.assertEqual(brief["brief_sha256"], brief_hash(brief))

    def test_input_source_and_protocol_hashes_are_current(self) -> None:
        brief = self.brief
        expected = brief["input_identities"]["source_hashes"]
        paths = {
            "cassi_qi_world.py": ROOT / "cassi_qi_world.py",
            "cassi-qi-flow-development.json": ROOT / "cassi-qi-flow-development.json",
            "cassi-qi-flow-canonical-fixtures.json": ROOT / "cassi-qi-flow-canonical-fixtures.json",
            "../CassiCosmos/project.godot": COSMOS / "project.godot",
            "../CassiCosmos/verify/run_all.gd": COSMOS / "verify" / "run_all.gd",
        }
        for logical, path in paths.items():
            self.assertTrue(path.is_file(), logical)
            self.assertEqual(expected[logical], sha256(path.read_bytes()), logical)
        self.assertEqual(brief["input_identities"]["protocol_hashes"]["cassi.qi-world-wire.v1"], WORLD_WIRE_REGISTRY_SHA256)
        self.assertEqual(brief["input_identities"]["schema_hashes"]["cassi.qi-world-wire.v1"], brief["input_identities"]["protocol_hashes"]["cassi.qi-world-wire-registry-canonical"])

    def test_registered_schema_and_fixed_config_fixture_hashes(self) -> None:
        brief = self.brief
        self.assertTrue(SCHEMA_REGISTRY_PATH.is_file())
        registry = json.loads(SCHEMA_REGISTRY_PATH.read_text(encoding="utf-8"))
        entry = registry["cassi.qi-flow-adapter-off-evidence.v1"]
        self.assertEqual(
            brief["input_identities"]["schema_hashes"]["cassi.qi-flow-adapter-off-evidence.v1"],
            sha256(canonical_json_bytes(entry)),
        )
        self.assertEqual(
            brief["input_identities"]["registered_fixture_set_sha256"],
            entry["canonical_fixture_set_sha256"],
        )
        self.assertEqual(
            brief["input_identities"]["adapter_config_sha256"],
            sha256(canonical_json_bytes(brief["adapter_config"])),
        )
        self.assertEqual(
            brief["input_identities"]["adapter_fixture_sha256"],
            sha256(canonical_json_bytes(brief["adapter_fixture"])),
        )
        self.assertEqual(brief["adapter_config"]["modalities"], ["audio", "optical", "proprioceptive"])
        self.assertEqual(brief["adapter_fixture"]["modalities"], brief["adapter_config"]["modalities"])

    def test_battery_is_the_exact_existing_runner_and_all_arms_are_present(self) -> None:
        brief = self.brief
        baseline = brief["battery_baseline"]
        self.assertEqual(baseline["scene_battery"], "../CassiCosmos/verify/run_all.gd")
        self.assertEqual(baseline["runner_arms_windowed"], True)
        self.assertEqual(baseline["godot_command"], [PINNED_GODOT, "--path", ".", "--headless", "-s", "res://verify/run_all.gd"])
        run_all = COSMOS / "verify" / "run_all.gd"
        text = run_all.read_text(encoding="utf-8")
        arms = re.findall(r'^\s*"([a-z0-9_]+)"\s*,?\s*$', text, re.MULTILINE)
        self.assertEqual(len(arms), baseline["expected_arms"])
        self.assertEqual(len(set(arms)), len(arms))
        self.assertNotIn("verify_qi_world_adapter", arms)

    def test_adapter_source_targets_remain_unedited_before_baseline(self) -> None:
        for path in ADAPTER_TARGETS:
            self.assertFalse(path.exists(), path)

    def test_conformance_vectors_and_no_peek_controls_are_explicit(self) -> None:
        brief = self.brief
        vectors = brief["python_godot_conformance"]["vectors"]
        self.assertEqual(
            {item["vector_id"] for item in vectors},
            {"world-identity", "wire-framing", "clock-tick", "body-frame", "no-peek", "default-off"},
        )
        self.assertEqual(
            brief["adapter_fixture"]["no_peek"],
            {"future_ticks": False, "candidate_consequences": False, "labels": False, "hidden_policy": False},
        )
        self.assertFalse(brief["artifact_contract"]["synthetic_evidence"])
        self.assertIn("battery-output.log", brief["artifact_contract"]["required_files"])
        self.assertIn("anchor.json", brief["artifact_contract"]["required_files"])


if __name__ == "__main__":
    unittest.main()
