"""Behavioral contract tests for the source-exact W5V/G5V artifact pipeline."""
from __future__ import annotations

import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Mapping

from cassi_qi_carrier import load_w4_carrier_profile
from cassi_qi_conversion import load_w5_conversion_profile, transition_w5_integrated
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_profile import canonical_hash, canonical_json_bytes, finite_float
from cassi_qi_topology import load_w4r_topology_profile
from cassi_qi_transport import load_w3_transport_profile
from run_cassi_qi_conversion import run_artifact as run_w5
from run_cassi_qi_conversion_viability import (
    ViabilityArtifactError,
    _state_from_raw,
    run_artifact as run_w5v,
)
from verify_cassi_qi_conversion_viability import VerificationError, verify


class W5VConversionViabilityTests(unittest.TestCase):
    """Exercise the immutable artifact rather than deriving proof from fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = tempfile.TemporaryDirectory(prefix="w5v-conversion-tests-")
        cls.base = Path(cls._temp.name)
        cls.w5_root = run_w5(output_root=cls.base / "w5")
        cls.artifact = run_w5v(w5_root=cls.w5_root, output_root=cls.base / "w5v")
        cls.verified = verify(cls.artifact)
        cls.geometry = load_w2_geometry_profile()
        cls.w5_profile = cls._json(cls.w5_root / "profile" / "conversion-profile.json")
        cls.profile = cls._json(cls.artifact / "profile" / "conversion-viability-profile.json")
        cls.receipt = cls._json(cls.artifact / "gates" / "g05v-conversion-viability" / "conversion-viability.json")
        extension_paths = sorted((cls.artifact / "certificate").glob("extension-*.json"))
        if len(extension_paths) != 1:
            raise AssertionError(f"expected one W5V extension, found {extension_paths}")
        cls.extension_path = extension_paths[0]
        cls.extension = cls._json(cls.extension_path)
        cls.parent_record = cls._json(cls.artifact / "run-spec" / "parent-w5.json")
        parent_extension_paths = [
            path
            for path in sorted((cls.artifact / "parents").glob("*.json"))
            if cls._json(path).get("schema") == "cassi.qi-flow-certificate-extension.v1"
        ]
        if len(parent_extension_paths) != 1:
            raise AssertionError(f"expected one W4R parent extension, found {parent_extension_paths}")
        cls.parent_extension_path = parent_extension_paths[0]
        cls.parent_extension = cls._json(cls.parent_extension_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _layout(profile: Mapping[str, Any]) -> dict[str, int]:
        raw = profile["state_layout"]
        return {
            "scale_count": int(raw["scale_count"]),
            "mode_count": int(raw["mode_count"]),
            "batch_limit": int(raw.get("batch_limit", raw.get("batch_lanes", 1))),
            "component_count": int(raw["component_count"]),
        }

    @staticmethod
    def _raw_offset(scale: int, component: int, mode: int, batch: int, layout: Mapping[str, int]) -> int:
        return ((scale * layout["component_count"] + component) * layout["mode_count"] + mode) * layout["batch_limit"] + batch

    @staticmethod
    def _cover_cells(profile: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        cover = profile["complete_domain_cover"]
        cells = cover.get("cells") if isinstance(cover, Mapping) else cover
        if not isinstance(cells, list):
            raise AssertionError("complete_domain_cover cells are not a list")
        return cells
    @classmethod
    def _fixture_raw(cls, fixture_id: str, name: str) -> bytes:
        control = cls._json(cls.w5_root / "gates" / "g05-conversion" / "controls" / f"{fixture_id}.json")
        descriptor = control["fixtures"][name]
        return (cls.w5_root / descriptor["path"]).read_bytes()

    def _copy_artifact(self, name: str) -> Path:
        destination = self.base / name
        shutil.copytree(self.artifact, destination)
        return destination

    def _tamper_json(self, root: Path, relative: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        path = root / relative
        value = self._json(path)
        mutate(value)
        path.write_bytes(canonical_json_bytes(value))

    def _assert_rejected(self, root: Path) -> None:
        with self.assertRaises(VerificationError):
            verify(root)

    def test_explicit_source_exact_binding_and_deterministic_replay(self) -> None:
        replay = run_w5v(w5_root=self.w5_root, output_root=self.base / "w5v")
        self.assertEqual(replay, self.artifact)
        self.assertEqual(verify(replay), self.verified)
        parent = self.parent_record
        self.assertTrue(parent["source_exact"])
        self.assertIsNone(parent["predecessor_w5v_forward_domain_certificate"])
        self.assertIsNone(parent["w5_engineering_binding"]["w5v_forward_domain_certificate"])
        self.assertEqual(parent["w5_engineering_binding"]["run_id"], self.verified["w5_run_id"])
        self.assertEqual(
            (self.artifact / "sources" / "cassi_qi_conversion.py").read_bytes(),
            (self.w5_root / "sources" / "cassi_qi_conversion.py").read_bytes(),
        )
        self.assertEqual(self.parent_record["w4r_extension_sha256"], self.parent_extension["self_sha256"])
        self.assertEqual(self.parent_record["w4r_chain_ordinal"] + 1, self.extension["chain_ordinal"])

    def test_parent_verifier_receipts_are_bound_into_status_and_index(self) -> None:
        index = self._json(self.artifact / "index.json")
        status = self._json(self.artifact / "gates" / "g05v-conversion-viability" / "status.json")
        receipts = index["parent_verifier_receipts"]
        self.assertEqual(receipts, status["parent_verifier_receipts"])
        self.assertEqual(index["parent_verifier_receipts_sha256"], status["parent_verifier_receipts_sha256"])
        self.assertEqual(receipts["schema"], "cassi.qi-flow-parent-verifier-receipts.v1")
        self.assertEqual(
            index["parent_verifier_receipts_sha256"],
            canonical_hash(receipts, "cassi.qi-flow-parent-verifier-receipts.v1"),
        )
        for name, result_schema in (
            ("w4r", "cassi.qi-flow-w4r-retention-core-run-index.v1"),
            ("w5", "cassi.qi-flow-w5-run-index.v1"),
        ):
            row = receipts[name]
            self.assertEqual(row["schema"], "cassi.qi-flow-parent-verification.v1")
            self.assertIsInstance(row["result"], dict)
            self.assertEqual(row["result"]["schema"], result_schema)
            self.assertEqual(
                row["verification_sha256"],
                canonical_hash(row["result"], "cassi.qi-flow-parent-verification.v1"),
            )
        nested = receipts["w5"]["result"]["parent_verifier_receipts"]
        self.assertEqual(
            nested,
            {
                "schema": "cassi.qi-flow-parent-verifier-receipts.v1",
                "w4r": receipts["w4r"],
            },
        )
        self.assertEqual(
            receipts["w5"]["result"]["parent_verifier_receipts_sha256"],
            canonical_hash(nested, "cassi.qi-flow-parent-verifier-receipts.v1"),
        )

    def test_complete_registered_cover_has_all_cells_and_no_unresolved(self) -> None:
        expected_ids = [
            "C00-exact-zero",
            "C01-balanced-memory-zero",
            "C02-balanced-memory-positive",
            "C03-neutral-positive",
            "C04-neutral-negative",
            "C05-progress-positive",
            "C06-progress-negative",
        ]
        cover = self._cover_cells(self.profile)
        self.assertEqual([row["cell_id"] for row in cover], expected_ids)
        self.assertEqual(
            self.profile["complete_domain_cover_semantics"]["cell_definition"],
            "D_nu=D_conv intersect predicate(cell_id)",
        )
        self.assertEqual(
            self.profile["complete_domain_cover_semantics"]["unspecified_coordinates"],
            "full frozen D_conv support subject only to cell predicate",
        )
        self.assertTrue(self.receipt["complete_cover"]["complete"])
        self.assertTrue(self.receipt["complete_cover"]["all_D_conv_coordinates_included"])
        self.assertTrue(self.receipt["complete_cover"]["interiors_pairwise_disjoint"])
        self.assertTrue(self.receipt["complete_cover"]["boundary_overlap_only"])
        self.assertEqual([row["cell_id"] for row in self.receipt["cells"]], expected_ids)
        self.assertEqual(self.receipt["cell_counts"], {"total": 7, "PASS": 7, "FAIL": 0, "UNRESOLVED": 0})
        self.assertFalse(any(row["unresolved"] for row in self.receipt["cells"]))

    def test_registered_cells_have_both_signs_and_exact_noops(self) -> None:
        rows = {row["cell_id"]: row for row in self.receipt["cells"]}
        self.assertEqual(rows["C05-progress-positive"]["classification"], "dissipative-imbalance-progress")
        self.assertEqual(rows["C06-progress-negative"]["classification"], "dissipative-imbalance-progress")
        self.assertTrue(rows["C05-progress-positive"]["sign_transfer_equals_sign_epsilon"])
        self.assertTrue(rows["C06-progress-negative"]["sign_transfer_equals_sign_epsilon"])
        self.assertTrue(rows["C01-balanced-memory-zero"]["exact_named_noop"])
        for fixture in ("empty", "balanced"):
            predecessor = self._fixture_raw(fixture, "predecessor")
            candidate = self._fixture_raw(fixture, "candidate")
            self.assertEqual(predecessor, candidate, fixture)

    def test_positive_memory_balance_keeps_map_lanes_and_relaxes_ema_once(self) -> None:
        fixture = "heterogeneous"
        predecessor_raw = self._fixture_raw(fixture, "predecessor")
        candidate_raw = self._fixture_raw(fixture, "candidate")
        predecessor = struct.unpack("<" + "d" * (len(predecessor_raw) // 8), predecessor_raw)
        candidate = struct.unpack("<" + "d" * (len(candidate_raw) // 8), candidate_raw)
        layout = self._layout({"state_layout": dict(self.geometry.base_profile.state_layout)})
        self.assertEqual(layout["component_count"], 9)
        expected_count = layout["scale_count"] * layout["component_count"] * layout["mode_count"] * layout["batch_limit"]
        self.assertEqual(len(predecessor), expected_count)
        for scale in range(layout["scale_count"]):
            for component in range(layout["component_count"] - 1):
                for mode in range(layout["mode_count"]):
                    for batch in range(layout["batch_limit"]):
                        offset = self._raw_offset(scale, component, mode, batch, layout)
                        self.assertEqual(predecessor[offset], candidate[offset])
        ema_pre = [
            predecessor[self._raw_offset(scale, layout["component_count"] - 1, mode, batch, layout)]
            for scale in range(layout["scale_count"])
            for mode in range(layout["mode_count"])
            for batch in range(layout["batch_limit"])
        ]
        ema_post = [
            candidate[self._raw_offset(scale, layout["component_count"] - 1, mode, batch, layout)]
            for scale in range(layout["scale_count"])
            for mode in range(layout["mode_count"])
            for batch in range(layout["batch_limit"])
        ]
        self.assertTrue(any(before > after >= 0.0 for before, after in zip(ema_pre, ema_post)))
        control = self._json(self.w5_root / "gates" / "g05-conversion" / "controls" / f"{fixture}.json")
        self.assertTrue(all(row["density_map_closure_abs"] == 0.0 for row in control["receipt"]["conversion"]["rows"]))
        boundary = {row["control_id"]: row for row in self.receipt["boundary_controls"]}
        self.assertEqual(boundary["balanced-positive-memory"]["analytic_outcome"]["T"], "f64:0000000000000000")
        self.assertEqual(boundary["balanced-positive-memory"]["expected_raw_relation"], "positions-and-velocities-exact-noop;EMA-physical-relaxation")

    def test_runtime_duration_endpoints_and_off_grid_rejection(self) -> None:
        geometry = self.geometry
        transport = load_w3_transport_profile(geometry=geometry)
        carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
        topology = load_w4r_topology_profile(geometry=geometry)
        conversion = load_w5_conversion_profile(
            geometry=geometry,
            parent_identities=self.w5_profile.get("parent_identities"),
        )
        certificate = self._json(self.w5_root / "certificate" / "g3n-certificate-root.json")
        source = self._fixture_raw("matched-energy-positive-imbalance", "predecessor")
        expected_rows = self.profile["exact_duration_rationals"]
        expected = tuple(row["numerator"] / row["denominator"] for row in expected_rows)
        self.assertEqual(conversion.runtime_durations, expected)
        self.assertEqual(conversion.h_min, expected[0])
        self.assertEqual(conversion.h_max, expected[-1])
        for duration in expected:
            step = transition_w5_integrated(
                _state_from_raw(source, geometry=geometry),
                geometry_profile=geometry,
                transport_profile=transport,
                carrier_profile=carrier,
                topology_profile=topology,
                conversion_profile=conversion,
                numerical_certificate=certificate,
                duration_s=duration,
            )
            self.assertTrue(step.committable)
        forbidden_duration = (expected[0] + expected[-1]) / 2.0
        self.assertNotIn(forbidden_duration, expected)
        forbidden = transition_w5_integrated(
            _state_from_raw(source, geometry=geometry),
            geometry_profile=geometry,
            transport_profile=transport,
            carrier_profile=carrier,
            topology_profile=topology,
            conversion_profile=conversion,
            numerical_certificate=certificate,
            duration_s=forbidden_duration,
        )
        self.assertFalse(forbidden.committable)
        self.assertEqual(forbidden.receipt["status"], "REJECTED")
        self.assertIn("exact registered member", forbidden.receipt["reason"])

    def test_coefficient_trials_enclose_all_physical_horizons_in_registered_order(self) -> None:
        candidates = self.profile["coefficient_candidates"]
        trials = self.receipt["coefficient_trials"]
        self.assertEqual([row["ordinal"] for row in trials], list(range(len(candidates))))
        self.assertEqual([row["epsilon_memory_time_s"] for row in trials], candidates)
        passing = [row for row in trials if row["status"] == "PASS"]
        selected = self.receipt["selected_coefficient"]
        self.assertEqual(selected, passing[0] if passing else None)
        if selected is not None:
            self.assertEqual(selected["epsilon_memory_time_s"], self.profile["physical_epsilon_memory_time_s"])
        for row in trials:
            self.assertEqual(len(row["duration_horizons"]), len(self.profile["exact_duration_rationals"]))
            if row["status"] == "PASS":
                tau_min = finite_float(row["tau_min_horizon"], name="tau min")
                tau_max = finite_float(row["tau_max_horizon"], name="tau max")
                self.assertGreater(tau_min, 0.0)
                self.assertLessEqual(tau_min, tau_max)
                self.assertLess(tau_max, 1.0)
                self.assertEqual(row["tau_asymptotic_horizon"], "f64:3ff0000000000000")
                self.assertGreaterEqual(
                    finite_float(row["ema_upper_slack_lower"], name="EMA slack"),
                    finite_float(self.profile["registered_margins"]["ema_upper_slack_min"], name="required EMA slack"),
                )

    def test_outward_enclosures_keep_density_nonnegative_ema_forward_and_registered_margins(self) -> None:
        bounds = self.receipt["analytic_enclosures"]
        coefficients = bounds["density_coefficients"]
        self.assertTrue(coefficients["all_nonnegative"])
        for name in ("one_minus_beta_min", "phi_beta_min", "beta_min", "one_minus_phi_beta_min"):
            self.assertGreaterEqual(finite_float(coefficients[name], name=name), 0.0)
        self.assertTrue(bounds["map_forward_inclusion"])
        self.assertLess(
            finite_float(bounds["epsilon2_post_max"], name="post EMA squared imbalance"),
            finite_float(bounds["ema_support_max"], name="EMA support"),
        )
        roundoff = bounds["runtime_roundoff_model"]
        operation_bound = self.profile["registered_margins"]["analytic_operation_count_upper"]
        self.assertEqual(roundoff["operation_count_upper"], operation_bound)
        self.assertIn("factored epsilon evaluation", roundoff["covers"])
        self.assertGreater(finite_float(roundoff["absolute_error_upper"], name="roundoff"), 0.0)
        progress_margin = finite_float(self.profile["registered_margins"]["Delta_T_min"], name="progress margin")
        neutral_margin = finite_float(self.profile["registered_margins"]["Delta_T_neutral"], name="neutral margin")
        cells = {row["cell_id"]: row for row in self.receipt["cells"]}
        for cell_id in ("C05-progress-positive", "C06-progress-negative"):
            self.assertGreaterEqual(finite_float(cells[cell_id]["transfer_margin_lower"], name=cell_id), progress_margin)
        for cell_id in ("C00-exact-zero", "C01-balanced-memory-zero", "C02-balanced-memory-positive", "C03-neutral-positive", "C04-neutral-negative"):
            self.assertGreaterEqual(finite_float(cells[cell_id]["transfer_margin_lower"], name=cell_id), 0.0)
        self.assertGreater(neutral_margin, 0.0)
        work = bounds["work_domain_proof"]
        self.assertEqual(work["algebraic_closure"], "Delta(E_total)-W_conversion=0")
        self.assertTrue(work["independent_raw_endpoint_replay_required"])

    def test_witnesses_are_hashed_raw_linkage_not_support_or_verdict(self) -> None:
        manifest = self._json(self.artifact / "gates" / "g05v-conversion-viability" / "witness-manifest.json")
        self.assertFalse(manifest["fixtures_define_support"])
        self.assertTrue(manifest["proof_cover_is_profile_registered"])
        receipt_witnesses = {row["fixture_id"]: row for row in self.receipt["witnesses"]}
        for row in manifest["witnesses"]:
            self.assertFalse(row["defines_support"])
            self.assertFalse(row["determines_cells"])
            self.assertFalse(row["determines_coefficient"])
            self.assertFalse(row["determines_verdict"])
            self.assertEqual(
                (self.artifact / row["predecessor_artifact_path"]).read_bytes(),
                (self.w5_root / row["predecessor_source_path"]).read_bytes(),
            )
            self.assertEqual(
                (self.artifact / row["candidate_artifact_path"]).read_bytes(),
                (self.w5_root / row["candidate_source_path"]).read_bytes(),
            )
            self.assertEqual(row["receipt_witness_sha256"], receipt_witnesses[row["fixture_id"]]["witness_sha256"])

    def test_certificate_extension_is_next_inventory_section_and_provisional(self) -> None:
        parent_ordinal = self.parent_extension["chain_ordinal"]
        self.assertEqual(self.extension["chain_ordinal"], parent_ordinal + 1)
        self.assertEqual(self.extension["chain_status"], "provisional")
        self.assertFalse(self.extension["production_certificate_complete"])
        self.assertIsNone(self.extension["final_certificate_identity_sha256"])
        self.assertIsInstance(self.extension["required_future_sections"], list)
        self.assertEqual(
            [row["ordinal"] for row in self.extension["parent_section_inventory"]],
            list(range(1, parent_ordinal + 1)),
        )
        self.assertEqual(
            [row["ordinal"] for row in self.extension["complete_section_inventory"]],
            list(range(1, self.extension["chain_ordinal"] + 1)),
        )
        self.assertEqual(self.extension["added_section"]["receipt_sha256"], self.receipt["self_sha256"])
        self.assertEqual(self.extension["added_section"]["all_cell_pass_count"], 7)
        self.assertEqual(self.extension["added_section"]["unresolved_count"], 0)

    def test_strict_verifier_rejects_semantic_source_parent_and_raw_witness_mutations(self) -> None:
        cover_path = "profile/conversion-viability-profile.json"

        def mutate_cell(value: dict[str, Any]) -> None:
            cells = value["complete_domain_cover"]
            if isinstance(cells, Mapping):
                cells = cells["cells"]
            cells[3]["predicate"] = "fixture-observed"

        mutations = {
            "support": (cover_path, lambda value: value["A_accepted"].__setitem__("density_sum_at_most", "f64:3ff0000000000000")),
            "cell": (cover_path, mutate_cell),
            "coefficient": (cover_path, lambda value: value["coefficient_candidates"].reverse()),
            "margin": (cover_path, lambda value: value["registered_margins"].__setitem__("Delta_T_min", "f64:0000000000000000")),
            "parent": (self.parent_extension_path.relative_to(self.artifact).as_posix(), lambda value: value.__setitem__("chain_ordinal", value["chain_ordinal"] + 90)),
        }
        for name, (relative, mutate) in mutations.items():
            with self.subTest(name=name):
                root = self._copy_artifact(f"mutated-{name}")
                self._tamper_json(root, relative, mutate)
                self._assert_rejected(root)
        source_root = self._copy_artifact("mutated-source")
        source = source_root / "sources" / "cassi_qi_conversion.py"
        source.write_bytes(source.read_bytes() + b"\n# mutation\n")
        self._assert_rejected(source_root)
        raw_root = self._copy_artifact("mutated-raw-witness")
        raw = raw_root / "witnesses" / "matched-energy-positive-imbalance-predecessor.f64le"
        payload = bytearray(raw.read_bytes())
        payload[0] ^= 1
        raw.write_bytes(bytes(payload))
        self._assert_rejected(raw_root)
        parent_root = self.base / "mutated-w5-parent"
        shutil.copytree(self.w5_root, parent_root)
        source_parent = parent_root / "sources" / "cassi_qi_conversion.py"
        source_parent.write_bytes(source_parent.read_bytes() + b"\n# source mutation\n")
        with self.assertRaises(ViabilityArtifactError):
            run_w5v(w5_root=parent_root, output_root=self.base / "w5v-source-mismatch")


if __name__ == "__main__":
    unittest.main()
