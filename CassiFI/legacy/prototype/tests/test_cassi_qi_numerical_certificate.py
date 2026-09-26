from __future__ import annotations

import copy
import json
import math
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_numerical_certificate import (
    CERTIFICATE_EXTENSION_SCHEMA,
    NUMERICAL_CERTIFICATE_DOMAIN,
    NUMERICAL_CERTIFICATE_SCHEMA,
    NUMERICAL_EXTENSION_DOMAIN,
    NUMERICAL_SECTION_SCHEMA,
    NumericalCertificateError,
    build_certificate_extension,
    build_numerical_certificate,
    build_registry_extension,
    evaluate_online_guard,
    raw_state_bytes_from_field,
    transition_v3_transport_guarded,
    validate_certificate_extension,
)
from cassi_qi_profile import canonical_hash, canonical_json_bytes, finite_float, load_development_profile
from cassi_qi_transport import load_w3_transport_profile, w3_stage_schedule
from run_cassi_qi_numerical_certificate import ARTIFACT_ROOT, ROOT, _discover_w3, run
from verify_cassi_qi_numerical_certificate import NumericalCertificateVerificationError, verify_artifact


class CertificateExtensionPrimitiveTests(unittest.TestCase):
    def test_builder_preserves_immutable_chain_rules(self) -> None:
        root_schema = "cassi.qi-flow-test-certificate-root.v1"
        root_domain = "cassi.qi-flow-test-certificate-root.v1"
        extension_schema = "cassi.qi-flow-test-certificate-extension.v1"
        extension_domain = "cassi.qi-flow-test-certificate-extension.v1"
        section_schema = "cassi.qi-flow-test-certificate-section.v1"
        section_domain = "cassi.qi-flow-test-certificate-section.v1"
        root = {
            "schema": root_schema,
            "certificate_chain_id": "test-chain",
            "chain_ordinal": 0,
            "parent_certificate_sha256": None,
            "complete_section_inventory": [],
            "chain_status": "provisional",
        }
        root["self_sha256"] = canonical_hash(root, root_domain)
        first = build_certificate_extension(
            parent=root,
            parent_schema=root_schema,
            parent_domain=root_domain,
            extension_schema=extension_schema,
            extension_domain=extension_domain,
            section_body={
                "schema": section_schema,
                "section_id": "test-first-section",
                "owning_package": "TEST",
                "gate": "GT",
            },
            section_schema=section_schema,
            section_domain=section_domain,
            owning_package="TEST",
            gate="GT",
            chain_status="final",
            final_certificate_identity=True,
            extra_fields={"test_parent_binding": root["self_sha256"]},
        )
        self.assertEqual(
            validate_certificate_extension(
                first,
                parent=root,
                parent_schema=root_schema,
                parent_domain=root_domain,
                extension_schema=extension_schema,
                extension_domain=extension_domain,
                section_schema=section_schema,
                section_domain=section_domain,
                final_certificate_identity=True,
            ),
            first,
        )
        appended = build_certificate_extension(
            parent=first,
            parent_schema=extension_schema,
            parent_domain=extension_domain,
            extension_schema="cassi.qi-flow-test-next-extension.v1",
            extension_domain="cassi.qi-flow-test-next-extension.v1",
            section_body={
                "schema": "cassi.qi-flow-test-next-section.v1",
                "section_id": "test-contiguous-section",
                "owning_package": "TEST",
                "gate": "GT",
            },
            section_schema="cassi.qi-flow-test-next-section.v1",
            section_domain="cassi.qi-flow-test-next-section.v1",
            owning_package="TEST",
            gate="GT",
            chain_status="provisional",
            final_certificate_identity=False,
        )
        self.assertEqual(appended["chain_ordinal"], 2)
        self.assertEqual(appended["parent_certificate_sha256"], first["self_sha256"])
        self.assertEqual(appended["parent_section_inventory"], [first["added_section"]])
        self.assertEqual(appended["complete_section_inventory"][-1], appended["added_section"])
        self.assertIsNone(appended["final_certificate_identity_sha256"])
        tampered = copy.deepcopy(appended)
        tampered["parent_section_inventory"] = []
        with self.assertRaises(NumericalCertificateError):
            validate_certificate_extension(
                tampered,
                parent=first,
                parent_schema=extension_schema,
                parent_domain=extension_domain,
                extension_schema="cassi.qi-flow-test-next-extension.v1",
                extension_domain="cassi.qi-flow-test-next-extension.v1",
                section_schema="cassi.qi-flow-test-next-section.v1",
                section_domain="cassi.qi-flow-test-next-section.v1",
                final_certificate_identity=False,
            )

    def test_numerical_builder_returns_a_valid_extension(self) -> None:
        profile = load_development_profile()
        geometry = load_w2_geometry_profile(base_profile=profile)
        transport = load_w3_transport_profile(geometry=geometry)
        certificate, extension = build_numerical_certificate(geometry=geometry, transport=transport)
        self.assertEqual(extension["chain_ordinal"], 1)
        self.assertEqual(extension["parent_certificate_sha256"], certificate["self_sha256"])
        self.assertEqual(extension["parent_section_inventory"], [])
        self.assertEqual(extension["complete_section_inventory"], [extension["added_section"]])
        self.assertEqual(extension["added_section"]["ordinal"], 1)
        self.assertEqual(extension["chain_status"], "final")
        self.assertIsInstance(extension["final_certificate_identity_sha256"], str)
        self.assertEqual(
            validate_certificate_extension(
                extension,
                parent=certificate,
                parent_schema=NUMERICAL_CERTIFICATE_SCHEMA,
                parent_domain=NUMERICAL_CERTIFICATE_DOMAIN,
                extension_schema=CERTIFICATE_EXTENSION_SCHEMA,
                extension_domain=NUMERICAL_EXTENSION_DOMAIN,
                section_schema=NUMERICAL_SECTION_SCHEMA,
                section_domain=NUMERICAL_SECTION_SCHEMA,
                final_certificate_identity=True,
            ),
            extension,
        )


class NumericalCertificateCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_development_profile()
        cls.geometry = load_w2_geometry_profile(base_profile=cls.profile)
        cls.transport = load_w3_transport_profile(geometry=cls.geometry)
        cls.w3_identity = _discover_w3(cls.transport)
        cls.certificate, cls.extension = build_numerical_certificate(
            geometry=cls.geometry,
            transport=cls.transport,
            accepted_w3_artifact_identity=cls.w3_identity,
        )

    def _state(self, batch: int = 1) -> QiFlowStateV3:
        return QiFlowStateV3.create(self.profile, batch_lanes=batch)

    def test_periodic_fft2_derivation_covers_every_scale(self) -> None:
        derivation = self.certificate["offline_derivation"]
        rows = derivation["inputs"]["per_scale"]
        sheets = self.geometry.payload["geometry_contract"]["per_scale_sheets"]
        self.assertEqual(len(rows), len(sheets))
        for row, sheet in zip(rows, sheets):
            self.assertEqual(row["active_shape_yx"], list(sheet["active_rectangle"]["shape_yx"]))
            self.assertEqual(row["signed_frequency_y"], list(sheet["signed_frequency_y"]))
            self.assertEqual(row["signed_frequency_x"], list(sheet["signed_frequency_x"]))
            ly = finite_float(row["extent_m"]["L_y"], name="Ly")
            lx = finite_float(row["extent_m"]["L_x"], name="Lx")
            expected = max(
                (2.0 * math.pi * ny / ly) ** 2 + (2.0 * math.pi * nx / lx) ** 2
                for ny in row["signed_frequency_y"]
                for nx in row["signed_frequency_x"]
            )
            observed = finite_float(row["k2_max_m2"], name="k2 max")
            self.assertLessEqual(abs(observed - expected), 8.0 * math.ulp(expected))
        self.assertEqual(derivation["derivation_formulae"]["laplacian"], "lambda(k)=-(kx^2+ky^2), k_axis=2*pi*n_axis/L_axis")
        self.assertEqual(derivation["inputs"]["workspace_unbounded_allocation"], "forbidden")

    def test_derivation_seals_uniform_clock_interval(self) -> None:
        derivation = self.certificate["offline_derivation"]
        inputs = derivation["inputs"]
        parameters = self.transport.pinned_parameters
        self.assertEqual(inputs["h_s"], inputs["h_min_s"])
        self.assertEqual(finite_float(inputs["h_min_s"], name="h_min_s"), parameters.h_min_s)
        self.assertEqual(finite_float(inputs["h_max_s"], name="h_max_s"), parameters.h_max_s)
        self.assertLess(parameters.h_min_s, parameters.h_max_s)
        stage_records = derivation["schedule_enclosure"]
        for stage, sealed in zip(w3_stage_schedule(parameters.h)["stages"], stage_records):
            ratio = finite_float(stage["duration_s"], name="stage duration") / parameters.h
            interval = sealed["duration_interval_s"]
            self.assertAlmostEqual(finite_float(interval["minimum"], name="stage h_min"), ratio * parameters.h_min_s, delta=math.ulp(parameters.h_min_s))
            self.assertAlmostEqual(finite_float(interval["maximum"], name="stage h_max"), ratio * parameters.h_max_s, delta=math.ulp(parameters.h_max_s))
            if "propagation" in sealed["name"] or "spectral" in sealed["name"]:
                self.assertGreaterEqual(finite_float(sealed["amplification"]["upper"], name="stage amplification"), math.sqrt(2.0))

    def test_guard_accepts_every_registered_batch_width(self) -> None:
        for batch in (1, int(self.certificate["online_guard_contract"]["raw_layout"]["batch_limit"])):
            receipt = evaluate_online_guard(self.certificate, raw_state=raw_state_bytes_from_field(self._state(batch).field))
            self.assertEqual(receipt["decision"], "ACCEPT")
            self.assertEqual(receipt["raw_layout"]["shape"][-1], batch)
            self.assertTrue(receipt["mutation_permitted"])

    def test_guard_boundaries_and_trust_boundary_rejections(self) -> None:
        layout = self.certificate["online_guard_contract"]["raw_layout"]
        shape_prefix = list(layout["shape_prefix"])
        raw = bytearray(math.prod([*shape_prefix, 1]) * 8)
        threshold = finite_float(self.certificate["online_guard_contract"]["raw_component_admission_abs"], name="threshold")
        struct.pack_into("<d", raw, 0, threshold)
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=bytes(raw))["decision"], "ACCEPT")
        struct.pack_into("<d", raw, 0, math.nextafter(threshold, math.inf))
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=bytes(raw))["reason"], "raw-component-envelope-exceeded")
        zero = raw_state_bytes_from_field(self._state().field)
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=zero, dtype="float32")["reason"], "dtype-mismatch")
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=zero, backend="gpu")["reason"], "backend-mismatch")
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=zero, source={"force": "f64:3f9eb851eb851eb8"})["reason"], "source-budget-exceeded")
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=b"bad")["reason"], "raw-layout-mismatch")
        too_many = bytes(math.prod([*shape_prefix, int(layout["batch_limit"]) + 1]) * 8)
        self.assertEqual(evaluate_online_guard(self.certificate, raw_state=too_many)["reason"], "raw-layout-mismatch")

    def test_mutated_certificate_is_not_a_substitute_derivation(self) -> None:
        tampered = copy.deepcopy(self.certificate)
        tampered["offline_derivation"]["precision"]["rounding"] = "nearest"
        with self.assertRaises(NumericalCertificateError):
            evaluate_online_guard(tampered, raw_state=raw_state_bytes_from_field(self._state().field))

    def test_guarded_transition_commits_or_rejects_before_mutation(self) -> None:
        state = self._state()
        predecessor = state.field.clone()
        accepted = transition_v3_transport_guarded(
            state,
            geometry_profile=self.geometry,
            transport_profile=self.transport,
            certificate=self.certificate,
        )
        self.assertTrue(accepted.committable)
        self.assertEqual(accepted.receipt["numerical_guard"]["decision"], "ACCEPT")
        self.assertTrue(state.field.equal(predecessor))
        rejected = transition_v3_transport_guarded(
            state,
            geometry_profile=self.geometry,
            transport_profile=self.transport,
            certificate=self.certificate,
            source={"force": "f64:3f9eb851eb851eb8"},
        )
        self.assertFalse(rejected.committable)
        self.assertIsNone(rejected.candidate)
        self.assertEqual(rejected.receipt["numerical_guard"]["reason"], "source-budget-exceeded")
        self.assertTrue(state.field.equal(predecessor))


    def test_registry_extension_is_ancestry_bound(self) -> None:
        record = build_registry_extension(parent_registry_sha256="a" * 64, parent_w1_run_id="b" * 64)
        self.assertEqual(record["parent_registry_sha256"], "a" * 64)
        self.assertEqual(record["parent_w1_run_id"], "b" * 64)
        self.assertEqual(len(record["entries"]), 3)
        self.assertEqual(record["entries"], sorted(record["entries"], key=lambda row: row["schema"]))


class NumericalCertificateArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run_result = run()
        cls.artifact = ROOT / cls.run_result["artifact"]

    def _copy(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory(prefix="w3n-test-", dir=ARTIFACT_ROOT)
        copied = Path(holder.name) / ".w3n-test-artifact"
        shutil.copytree(self.artifact, copied)
        return holder, copied

    def test_source_exact_artifact_passes_independent_replay(self) -> None:
        receipt = verify_artifact(self.artifact)
        self.assertEqual(receipt["status"], "PASS_W3N_G3N")
        self.assertEqual(receipt["guard_case_count"], 11)
        self.assertEqual(receipt["run_id"], self.run_result["run_id"])

    def test_raw_fixture_tamper_is_rejected(self) -> None:
        holder, copied = self._copy()
        try:
            path = copied / "fixtures" / "accepted.f64le"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            with self.assertRaises(NumericalCertificateVerificationError):
                verify_artifact(copied)
        finally:
            holder.cleanup()

    def test_source_snapshot_tamper_is_rejected(self) -> None:
        holder, copied = self._copy()
        try:
            path = copied / "sources" / "cassi_qi_numerical_certificate.py"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaises(NumericalCertificateVerificationError):
                verify_artifact(copied)
        finally:
            holder.cleanup()
    def test_clock_interval_mutation_is_rejected(self) -> None:
        holder, copied = self._copy()
        try:
            path = copied / "certificate" / "certificate-root.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            inputs = record["offline_derivation"]["inputs"]
            inputs["h_max_s"] = inputs["h_min_s"]
            path.write_bytes(canonical_json_bytes(record))
            with self.assertRaises(NumericalCertificateVerificationError):
                verify_artifact(copied)
        finally:
            holder.cleanup()

    def test_max_duration_enclosure_mutation_is_rejected(self) -> None:
        holder, copied = self._copy()
        try:
            path = copied / "certificate" / "certificate-root.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            propagation = next(
                row
                for row in record["offline_derivation"]["schedule_enclosure"]
                if "propagation" in row["name"] or "spectral" in row["name"]
            )
            propagation["amplification"]["upper"] = propagation["amplification"]["lower"]
            path.write_bytes(canonical_json_bytes(record))
            with self.assertRaises(NumericalCertificateVerificationError):
                verify_artifact(copied)
        finally:
            holder.cleanup()

    def test_duplicate_json_key_is_rejected(self) -> None:
        holder, copied = self._copy()
        try:
            path = copied / "index.json"
            raw = path.read_text(encoding="utf-8")
            path.write_text(raw.replace("{", "{\"schema\":\"duplicate\",", 1), encoding="utf-8")
            with self.assertRaises(NumericalCertificateVerificationError):
                verify_artifact(copied)
        finally:
            holder.cleanup()


if __name__ == "__main__":
    unittest.main()
