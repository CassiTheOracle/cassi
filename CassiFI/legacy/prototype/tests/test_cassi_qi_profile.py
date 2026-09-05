from __future__ import annotations

from collections.abc import Mapping
import copy
from fractions import Fraction
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import cassi_qi_profile as profile


def _leaf_pointers(value: object, prefix: str = "") -> set[str]:
    if isinstance(value, Mapping):
        result: set[str] = set()
        for key in value:
            result.update(_leaf_pointers(value[key], f"{prefix}/{key}"))
        return result
    if isinstance(value, list):
        return {prefix}
    return {prefix}


class ProfileContractTests(unittest.TestCase):
    def test_development_profile_opens_fixed_parent_root(self) -> None:
        item = profile.load_development_profile(
            Path(__file__).with_name("cassi-qi-flow-development.json")
        )
        root = profile.build_contract_root(item)
        self.assertEqual(profile.validate_contract_root(root).sha256, item.contract_root_sha256)
        self.assertEqual(item.state_layout["shape"], [4, 288, None])
        self.assertEqual(len(item.semantic_subhashes), len(profile.SEMANTIC_PROJECTIONS))

    def test_contract_root_is_invariant_across_profile_ids_and_overrides(self) -> None:
        baseline = profile.QiFlowProfile.from_defaults(profile_id="root-invariance-a")
        renamed = profile.QiFlowProfile.from_defaults(profile_id="root-invariance-b")
        overridden = profile.QiFlowProfile.from_defaults(
            profile_id="root-invariance-a",
            overrides={"action": {"max_candidates": 7}},
        )
        self.assertEqual(
            baseline.contract_root_sha256,
            profile.build_contract_root().sha256,
        )
        self.assertEqual(baseline.contract_root_sha256, renamed.contract_root_sha256)
        self.assertEqual(baseline.contract_root_sha256, overridden.contract_root_sha256)
        self.assertNotEqual(baseline.profile_sha256, renamed.profile_sha256)
        self.assertNotEqual(baseline.profile_sha256, overridden.profile_sha256)

    def test_every_projection_owns_the_contract_root(self) -> None:
        projections = profile.PROJECTION_REGISTRY["projections"]
        self.assertEqual(
            [record["name"] for record in projections],
            list(profile.SEMANTIC_PROJECTIONS),
        )
        for projection in projections:
            self.assertIn("/contract_root_sha256", projection["pointers"])
            owns_profile_id = projection["name"] in {
                "session_storage_sha256",
                "provider_api_sha256",
                "security_evidence_sha256",
            }
            self.assertEqual("/profile_id" in projection["pointers"], owns_profile_id)

    def test_every_materialized_profile_leaf_has_declared_projection_ownership(self) -> None:
        expected = _leaf_pointers(dict(profile.PROFILE_DEFAULTS))
        expected.update({"/profile_id", "/contract_root_sha256"})
        declared: dict[str, set[str]] = {}
        for projection in profile.PROJECTION_REGISTRY["projections"]:
            for pointer in projection["pointers"]:
                declared.setdefault(pointer, set()).add(projection["name"])
        self.assertEqual(set(declared), expected)
        self.assertTrue(all(owners for owners in declared.values()))
        registered_fields = profile.PROJECTION_REGISTRY["fields"]
        self.assertEqual(
            {field["json_pointer"] for field in registered_fields},
            expected,
        )
        for field in registered_fields:
            self.assertEqual(set(field["consumers"]), declared[field["json_pointer"]])

    def test_physical_geometry_clock_and_runtime_source_identities_are_exact(self) -> None:
        item = profile.load_development_profile(
            Path(__file__).with_name("cassi-qi-flow-development.json")
        )
        payload = item.payload
        field = payload["field"]
        spatial = payload["spatial"]
        self.assertEqual(field["active_shapes"], [[4, 8]] * 4)
        self.assertEqual(field["active_site_counts"], [32] * 4)
        self.assertEqual(field["mode_count"], 32)
        self.assertEqual(
            spatial["geometry_operator_sha256"],
            payload["scale_geometry"]["state_operator"]["selected_operator_sha256"],
        )
        for shape, sheet, area in zip(
            field["active_shapes"],
            spatial["per_scale"],
            spatial["metric_cell_area"],
            strict=True,
        ):
            self.assertEqual(sheet["active_shape"], shape)
            self.assertEqual(sheet["active_site_count"], shape[0] * shape[1])
            dx = profile.finite_float(sheet["spacing_m"]["dx"])
            dy = profile.finite_float(sheet["spacing_m"]["dy"])
            lx = profile.finite_float(sheet["extent_m"]["L_x"])
            ly = profile.finite_float(sheet["extent_m"]["L_y"])
            self.assertGreater(dx, 0.0)
            self.assertGreater(dy, 0.0)
            self.assertAlmostEqual(lx, dx * shape[1])
            self.assertAlmostEqual(ly, dy * shape[0])
            self.assertAlmostEqual(profile.finite_float(area), dx * dy)

        clock = payload["execution"]["clock"]
        self.assertEqual(clock["schema"], "cassi.qi-flow-clock-time.v1")
        self.assertEqual(clock["unit"], "second")
        self.assertEqual(Fraction(**clock["h_min"]), Fraction(1, 1000))
        self.assertEqual(Fraction(**clock["h_max"]), Fraction(1, 100))
        schedule = payload["execution"]["schedule"]
        total_advance = sum(
            (
                Fraction(
                    stage["clock_increment_num"],
                    stage["clock_increment_den"],
                )
                for stage in schedule["stages"]
            ),
            Fraction(),
        )
        self.assertEqual(total_advance, Fraction(1))
        self.assertEqual(
            Fraction(
                schedule["total_clock_increment_num"],
                schedule["total_clock_increment_den"],
            ),
            Fraction(1),
        )

        runtime_source = copy.deepcopy(payload["execution"]["source_identity"])
        source_self_sha256 = runtime_source.pop("self_sha256")
        self.assertEqual(
            source_self_sha256,
            profile.canonical_hash(runtime_source, runtime_source["schema"]),
        )
        self.assertEqual(source_self_sha256, item.source_identity_sha256)
        self.assertEqual(runtime_source["enabled_streams"], [])
        self.assertEqual(runtime_source["maximum_source_bytes_per_step"], 0)
        self.assertEqual(runtime_source["clock_id"], "physical-rational-seconds-v1")

    def test_canonical_codec_rejects_duplicate_nonfinite_surrogate_and_negative_zero(self) -> None:
        for payload in (
            b'{"x":1,"x":2}',
            b'{"x":NaN}',
            b'{"x":1.5}',
            b'{"x":"f64:8000000000000000"}',
            b"\xff",
        ):
            with self.assertRaises(profile.CanonicalCodecError):
                profile.canonical_json_loads(payload)
        with self.assertRaises(profile.CanonicalCodecError):
            profile.canonical_json_bytes({"x": math.nan})
        with self.assertRaises(profile.CanonicalCodecError):
            profile.canonical_json_bytes({"x": "\ud800"})
        with self.assertRaises(profile.CanonicalCodecError):
            profile.finite_float("f64:8000000000000000")

    def test_canonical_hash_domain_separates_same_payload(self) -> None:
        self.assertNotEqual(
            profile.canonical_hash({"same": 1}, "one"),
            profile.canonical_hash({"same": 1}, "two"),
        )
        self.assertEqual(profile.canonical_json_bytes({"b": 1, "a": 2}), b'{"a":2,"b":1}')
        encoded = profile.canonical_json_bytes({"value": 1.5})
        self.assertEqual(encoded, b'{"value":"f64:3ff8000000000000"}')
        self.assertEqual(profile.finite_float("f64:3ff8000000000000"), 1.5)

    def test_root_rejects_self_hash_and_defaults_mutation(self) -> None:
        root = profile.build_contract_root(profile.load_development_profile())
        tampered = root.to_dict()
        tampered["self_sha256"] = "0" * 64
        with self.assertRaises(profile.PROFILE_MISMATCH):
            profile.validate_contract_root(tampered)
        tampered = root.to_dict()
        tampered["profile_defaults"] = copy.deepcopy(tampered["profile_defaults"])
        tampered["profile_defaults"]["sha256"] = "0" * 64
        tampered["self_sha256"] = profile.canonical_hash(
            {key: value for key, value in tampered.items() if key != "self_sha256"},
            profile.CONTRACT_ROOT_BOOTSTRAP_SCHEMA,
        )
        with self.assertRaises(profile.PROFILE_MISMATCH):
            profile.validate_contract_root(tampered)

    def test_root_rejects_reordered_noncanonical_bytes(self) -> None:
        root = profile.build_contract_root(profile.load_development_profile()).to_dict()
        reordered = json.dumps(root, ensure_ascii=False, sort_keys=False, separators=(",", ":")).encode("utf-8")
        with self.assertRaises(profile.CanonicalCodecError):
            profile.validate_contract_root(reordered)

    def test_omitted_unknown_and_nested_defaults_fail(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            payload = {
                "schema": "cassi.qi-flow-development-config.v1",
                "w0_run_id": profile.W0_RUN_ID,
                "historical_manifest_sha256": profile.W0_HISTORICAL_MANIFEST_SHA256,
                "profile": {"profile_id": "bad"},
            }
            path.write_bytes(profile.canonical_json_bytes(payload))
            with self.assertRaises(profile.PROFILE_MISMATCH):
                profile.load_development_profile(path)
            payload["schema"] = "cassi.qi-flow-development-config.v2"
            path.write_bytes(profile.canonical_json_bytes(payload))
            with self.assertRaises(profile.PROFILE_MISMATCH):
                profile.load_development_profile(path)

            payload = profile.canonical_json_loads(
                Path(__file__).with_name("cassi-qi-flow-development.json").read_bytes()
            )
            payload["profile"]["field"]["state_bounds"]["undeclared"] = "f64:0000000000000000"
            path.write_bytes(profile.canonical_json_bytes(payload))
            with self.assertRaises(profile.PROFILE_MISMATCH):
                profile.load_development_profile(path)

        candidate = copy.deepcopy(dict(profile.QiFlowProfile.from_defaults().payload))
        candidate["field"]["state_bounds"]["undeclared"] = "f64:0000000000000000"
        with self.assertRaises(profile.PROFILE_MISMATCH):
            profile.validate_profile(candidate)

    def test_development_config_cannot_select_a_modified_profile(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            payload = profile.canonical_json_loads(
                Path(__file__).with_name("cassi-qi-flow-development.json").read_bytes()
            )
            payload["profile"]["dynamics"]["clock"]["h_max"] = "f64:3ff0000000000000"
            path.write_bytes(profile.canonical_json_bytes(payload))
            with self.assertRaises(profile.PROFILE_MISMATCH):
                profile.load_development_profile(path)

    def test_profile_root_mismatch_is_explicit(self) -> None:
        item = profile.QiFlowProfile.from_defaults(
            overrides={"action": {"max_candidates": 7}}
        )
        forged = profile.QiFlowProfile(
            item.payload,
            profile.ContractRoot({**item.contract_root.payload, "self_sha256": "0" * 64}),
            item.profile_sha256,
            item.semantic_subhashes,
            item.state_layout,
        )
        with self.assertRaises(profile.PROFILE_MISMATCH):
            profile.build_contract_root(forged)

    def test_comparison_evidence_is_profile_acyclic(self) -> None:
        first = profile.QiFlowProfile.from_defaults(profile_id="comparison-a")
        second = profile.QiFlowProfile.from_defaults(profile_id="comparison-b")
        first_evidence = first.payload["scale_geometry"]["selection_evidence"]
        second_evidence = second.payload["scale_geometry"]["selection_evidence"]
        self.assertIsNone(first_evidence["comparison_receipt_sha256"])
        self.assertEqual(first_evidence, second_evidence)
        self.assertNotIn("profile_sha256", first_evidence)
        self.assertNotIn("contract_root_sha256", first_evidence)
        self.assertNotEqual(first.profile_sha256, second.profile_sha256)

    def test_bootstrap_fixture_corpus_passes(self) -> None:
        profile.bootstrap_self_test()
        identity = profile.bootstrap_identity()
        self.assertEqual(identity["schema"], profile.CONTRACT_ROOT_BOOTSTRAP_SCHEMA)
        self.assertEqual(len(identity["source_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
