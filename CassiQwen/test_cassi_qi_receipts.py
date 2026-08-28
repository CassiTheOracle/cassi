from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Mapping
from typing import Any

import cassi_qi_receipts as receipts
from cassi_qi_profile import (
    PROFILE_MISMATCH,
    SCHEMA_REGISTRY,
    canonical_hash,
    canonical_json_bytes,
    load_development_profile,
)


class ReceiptSchemaTests(unittest.TestCase):
    _CUSTOM_SCHEMA = "cassi.qi-flow-test-receipt.v1"
    _CUSTOM_FIXTURE_ID = "receipt-schema-fixtures-v1"
    _ENVELOPE = frozenset(
        {
            "schema",
            "receipt_id",
            "contract_root_sha256",
            "profile_sha256",
            "consumed_semantic_subhashes",
            "self_sha256",
        }
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_development_profile()
        cls.root = cls.profile.contract_root

    @staticmethod
    def _seal(record: Mapping[str, Any], schema: str) -> dict[str, Any]:
        result = copy.deepcopy(dict(record))
        result.pop("receipt_id", None)
        result.pop("self_sha256", None)
        result["receipt_id"] = canonical_hash(result, f"{schema}.receipt-id")
        self_material = dict(result)
        self_material.pop("self_sha256", None)
        result["self_sha256"] = canonical_hash(self_material, schema)
        return result

    @staticmethod
    def _sha(char: str) -> str:
        return char * 64

    @classmethod
    def _custom_registry(cls) -> dict[str, Any]:
        schema = cls._CUSTOM_SCHEMA
        parents = list(receipts.SEMANTIC_PARENT_ORDER[:2])
        digest = {"type": "string", "format": "sha256", "max_bytes": 64}
        plain = {"type": "string", "format": "plain", "max_bytes": 64}
        parent_row = {
            "type": "object",
            "required_keys": ["name", "sha256"],
            "optional_keys": [],
            "nullable_keys": [],
            "properties": {
                "name": {"type": "enum", "values": parents},
                "sha256": digest,
            },
        }
        properties = {
            "schema": {"type": "enum", "values": [schema]},
            "receipt_id": digest,
            "contract_root_sha256": digest,
            "profile_sha256": digest,
            "consumed_semantic_subhashes": {
                "type": "array",
                "min_items": len(parents),
                "max_items": len(parents),
                "items": parent_row,
            },
            "required_label": plain,
            "nested": {
                "type": "object",
                "required_keys": ["count"],
                "optional_keys": ["note"],
                "nullable_keys": [],
                "properties": {
                    "count": {"type": "integer", "minimum": 0, "maximum": 32},
                    "note": plain,
                },
            },
            "fixture_id": {"type": "string", "format": "id", "max_bytes": 128},
            "optional_note": plain,
            "nullable_note": plain,
            "self_sha256": digest,
        }
        document: dict[str, Any] = {
            "schema": receipts.SCHEMA_DOCUMENT_SCHEMA,
            "object_schema": schema,
            "required_keys": [
                "consumed_semantic_subhashes",
                "contract_root_sha256",
                "nested",
                "profile_sha256",
                "receipt_id",
                "required_label",
                "schema",
                "self_sha256",
            ],
            "optional_keys": ["fixture_id", "nullable_note", "optional_note"],
            "nullable_keys": ["nullable_note"],
            "properties": properties,
            "invariants": [
                "Every indexed receipt binds the selected contract root and profile.",
                "Semantic parent rows are ordered by the frozen registry parent order.",
            ],
        }

        def fixture(*, maximal: bool = False, nullable: bool = False) -> dict[str, Any]:
            value: dict[str, Any] = {
                "schema": schema,
                "contract_root_sha256": cls._sha("0"),
                "profile_sha256": cls._sha("1"),
                "consumed_semantic_subhashes": [
                    {"name": name, "sha256": cls._sha(str(index + 2))}
                    for index, name in enumerate(parents)
                ],
                "required_label": "fixture",
                "nested": {"count": 0},
            }
            if maximal or nullable:
                value.update(
                    {
                        "fixture_id": cls._CUSTOM_FIXTURE_ID,
                        "optional_note": "maximal",
                        "nullable_note": None if nullable else "present",
                    }
                )
            return cls._seal(value, schema)

        fixture_set = {
            "minimal_valid": fixture(),
            "maximal_valid": fixture(maximal=True),
            "nullable_valid": [fixture(nullable=True)],
        }
        controls = {
            "schema_under_test": schema,
            "controls": [
                {
                    "control_id": "unknown-key",
                    "base_fixture": "minimal_valid",
                    "mutation": {"op": "add", "path": "/unexpected", "value": "x"},
                    "expected_error_code": "UNKNOWN_KEY",
                }
            ],
        }
        entry: dict[str, Any] = {
            "schema": schema,
            "version": 1,
            "object_class": "indexed-receipt",
            "lifecycle": "transaction_evidence",
            "max_encoded_bytes": 4096,
            "max_fanout": 32,
            "semantic_parent_names": parents,
            "schema_document": document,
            "schema_document_sha256": canonical_hash(document, receipts.SCHEMA_DOCUMENT_SCHEMA),
            "fixture_id": cls._CUSTOM_FIXTURE_ID,
            "canonical_fixture_set": fixture_set,
            "canonical_fixture_set_sha256": canonical_hash(
                fixture_set,
                receipts.SCHEMA_FIXTURE_SET_HASH_DOMAIN,
            ),
            "mutation_controls": controls,
            "mutation_controls_sha256": canonical_hash(
                controls,
                receipts.SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN,
            ),
            "hash_domain": schema,
            "self_hash_field": "self_sha256",
            "independent_verifier": "stdlib-schema-replay-v1",
            "migration_policy": "new-schema-version-and-contract-root-v1",
        }
        registry = {"schema": receipts.SCHEMA_REGISTRY_SCHEMA, "registry_id": "qi-flow-schema-registry-v1", "entries": [entry]}
        registry["self_sha256"] = canonical_hash(registry, receipts.SCHEMA_REGISTRY_SCHEMA)
        return registry

    def _custom_receipt(self, registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return receipts.build_receipt(
            self._CUSTOM_SCHEMA,
            {
                "required_label": "runtime-label",
                "nested": {"count": 1},
            },
            contract_root=self.root,
            profile=self.profile,
            schema_registry=self._custom_registry() if registry is None else registry,
        )

    def _assert_rejected(
        self,
        receipt: Mapping[str, Any] | bytes | str,
        registry: Mapping[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        with self.assertRaises(PROFILE_MISMATCH) as raised:
            receipts.validate_receipt(
                receipt,
                contract_root=self.root,
                profile=self.profile,
                schema_registry=self._custom_registry() if registry is None else registry,
                expected_schema=self._CUSTOM_SCHEMA,
            )
        if code is not None:
            self.assertTrue(str(raised.exception).startswith(f"{code}:"), str(raised.exception))

    @staticmethod
    def _entry(schema: str) -> Mapping[str, Any]:
        matches = [entry for entry in SCHEMA_REGISTRY["entries"] if entry["schema"] == schema]
        if len(matches) != 1:
            raise AssertionError(f"registered schema is not unique: {schema}")
        return matches[0]

    def test_named_builders_round_trip_only_live_indexed_receipts(self) -> None:
        self.assertTrue(receipts.RECEIPT_SCHEMAS)
        registry_schemas = {
            entry["schema"]
            for entry in SCHEMA_REGISTRY["entries"]
            if entry.get("object_class") == "indexed-receipt"
        }
        self.assertEqual(set(receipts.RECEIPT_SCHEMAS.values()), registry_schemas)
        for kind, schema in receipts.RECEIPT_SCHEMAS.items():
            with self.subTest(kind=kind, schema=schema):
                entry = self._entry(schema)
                fixture = copy.deepcopy(entry["canonical_fixture_set"]["minimal_valid"])
                payload = {name: value for name, value in fixture.items() if name not in self._ENVELOPE}
                builder = getattr(receipts, f"build_{kind}_receipt")
                validator = getattr(receipts, f"validate_{kind}_receipt")
                receipt = builder(payload, contract_root=self.root, profile=self.profile)
                self.assertEqual(validator(receipt, contract_root=self.root, profile=self.profile), receipt)
                self.assertEqual(receipts.validate_receipt(receipt, contract_root=self.root, profile=self.profile), receipt)
                self.assertEqual(receipts.receipt_bytes(receipt, contract_root=self.root, profile=self.profile), canonical_json_bytes(receipt))

    def test_rejects_every_registered_nonreceipt_schema(self) -> None:
        schema = next(entry["schema"] for entry in SCHEMA_REGISTRY["entries"] if entry.get("object_class") != "indexed-receipt")
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^OBJECT_CLASS_MISMATCH:"):
            receipts.build_receipt(schema, {}, contract_root=self.root, profile=self.profile)

    def test_exact_recursive_shape_and_nullable_contract(self) -> None:
        registry = self._custom_registry()
        receipt = self._custom_receipt(registry)
        self.assertEqual(
            receipts.validate_receipt(
                receipt,
                contract_root=self.root,
                profile=self.profile,
                schema_registry=registry,
                expected_schema=self._CUSTOM_SCHEMA,
            ),
            receipt,
        )

        nullable = copy.deepcopy(receipt)
        nullable["nullable_note"] = None
        nullable = self._seal(nullable, self._CUSTOM_SCHEMA)
        self.assertIsNone(
            receipts.validate_receipt(
                nullable,
                contract_root=self.root,
                profile=self.profile,
                schema_registry=registry,
                expected_schema=self._CUSTOM_SCHEMA,
            )["nullable_note"]
        )

        variants: dict[str, tuple[dict[str, Any], str]] = {}
        unknown = copy.deepcopy(receipt)
        unknown["undeclared"] = "x"
        variants["unknown"] = (self._seal(unknown, self._CUSTOM_SCHEMA), "UNKNOWN_KEY")
        missing = copy.deepcopy(receipt)
        del missing["required_label"]
        variants["missing"] = (self._seal(missing, self._CUSTOM_SCHEMA), "MISSING_REQUIRED_KEY")
        nonnullable = copy.deepcopy(receipt)
        nonnullable["required_label"] = None
        variants["nonnullable"] = (self._seal(nonnullable, self._CUSTOM_SCHEMA), "FORBIDDEN_NULL")
        nested_unknown = copy.deepcopy(receipt)
        nested_unknown["nested"]["undeclared"] = "x"
        variants["nested_unknown"] = (self._seal(nested_unknown, self._CUSTOM_SCHEMA), "UNKNOWN_KEY")
        nested_missing = copy.deepcopy(receipt)
        del nested_missing["nested"]["count"]
        variants["nested_missing"] = (self._seal(nested_missing, self._CUSTOM_SCHEMA), "MISSING_REQUIRED_KEY")
        for name, (variant, code) in variants.items():
            with self.subTest(variant=name):
                self._assert_rejected(variant, registry, code)

    def test_identity_envelope_requires_root_profile_parent_order_and_derived_ids(self) -> None:
        registry = self._custom_registry()
        receipt = self._custom_receipt(registry)
        variants: dict[str, tuple[dict[str, Any], str]] = {}

        reordered = copy.deepcopy(receipt)
        reordered["consumed_semantic_subhashes"].reverse()
        variants["parent_order"] = (self._seal(reordered, self._CUSTOM_SCHEMA), "SEMANTIC_PARENT_ORDER_MISMATCH")
        wrong_parent = copy.deepcopy(receipt)
        wrong_parent["consumed_semantic_subhashes"][0]["sha256"] = self._sha("f")
        variants["parent_digest"] = (self._seal(wrong_parent, self._CUSTOM_SCHEMA), "SEMANTIC_PARENT_DIGEST_MISMATCH")
        wrong_root = copy.deepcopy(receipt)
        wrong_root["contract_root_sha256"] = self._sha("f")
        variants["root"] = (self._seal(wrong_root, self._CUSTOM_SCHEMA), "HASH_DOMAIN_MISMATCH")
        wrong_profile = copy.deepcopy(receipt)
        wrong_profile["profile_sha256"] = self._sha("f")
        variants["profile"] = (self._seal(wrong_profile, self._CUSTOM_SCHEMA), "HASH_DOMAIN_MISMATCH")
        wrong_receipt_id = copy.deepcopy(receipt)
        wrong_receipt_id["receipt_id"] = self._sha("f")
        wrong_receipt_id["self_sha256"] = canonical_hash(
            {name: value for name, value in wrong_receipt_id.items() if name != "self_sha256"},
            self._CUSTOM_SCHEMA,
        )
        variants["receipt_id"] = (wrong_receipt_id, "RECEIPT_ID_MISMATCH")
        wrong_self = copy.deepcopy(receipt)
        wrong_self["self_sha256"] = self._sha("f")
        variants["self"] = (wrong_self, "SELF_HASH_MISMATCH")
        legacy = copy.deepcopy(receipt)
        legacy["domain"] = "legacy"
        variants["legacy"] = (self._seal(legacy, self._CUSTOM_SCHEMA), "UNKNOWN_KEY")
        for name, (variant, code) in variants.items():
            with self.subTest(variant=name):
                self._assert_rejected(variant, registry, code)

    def test_canonical_input_and_payload_limits_are_not_normalized(self) -> None:
        registry = self._custom_registry()
        receipt = self._custom_receipt(registry)
        self._assert_rejected(b" " + canonical_json_bytes(receipt), registry, "NONCANONICAL_ENCODING")
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^NONCANONICAL_ENCODING:"):
            receipts.build_receipt(
                self._CUSTOM_SCHEMA,
                {"required_label": "x", "nested": {"count": 1 << 53}},
                contract_root=self.root,
                profile=self.profile,
                schema_registry=registry,
            )
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^NONCANONICAL_ENCODING:"):
            receipts.build_receipt(
                self._CUSTOM_SCHEMA,
                {"required_label": 1.0, "nested": {"count": 1}},
                contract_root=self.root,
                profile=self.profile,
                schema_registry=registry,
            )
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^UNKNOWN_KEY:"):
            receipts.build_receipt(
                self._CUSTOM_SCHEMA,
                {"receipt_id": self._sha("0"), "required_label": "x", "nested": {"count": 1}},
                contract_root=self.root,
                profile=self.profile,
                schema_registry=registry,
            )

    def test_schema_document_fixture_set_and_control_hashes_are_evidence(self) -> None:
        receipt = self._custom_receipt()
        wrong_registry_id = self._custom_registry()
        wrong_registry_id["registry_id"] = "other-registry-v1"
        wrong_registry_id["self_sha256"] = canonical_hash(
            {name: value for name, value in wrong_registry_id.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, wrong_registry_id, "SCHEMA_LITERAL_MISMATCH")
        inline_document_self = self._custom_registry()
        inline_document_self["entries"][0]["schema_document"]["self_sha256"] = self._sha("0")
        inline_document_self["self_sha256"] = canonical_hash(
            {name: value for name, value in inline_document_self.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, inline_document_self, "UNKNOWN_KEY")
        missing_invariants = self._custom_registry()
        del missing_invariants["entries"][0]["schema_document"]["invariants"]
        missing_invariants["self_sha256"] = canonical_hash(
            {name: value for name, value in missing_invariants.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, missing_invariants, "UNKNOWN_KEY")
        wrong_invariant = self._custom_registry()
        wrong_invariant["entries"][0]["schema_document"]["invariants"][0] = "Altered invariant."
        wrong_invariant["self_sha256"] = canonical_hash(
            {name: value for name, value in wrong_invariant.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, wrong_invariant, "SELF_HASH_MISMATCH")


        wrong_document = self._custom_registry()
        wrong_document["entries"][0]["schema_document"]["properties"]["required_label"]["max_bytes"] = 63
        wrong_document["self_sha256"] = canonical_hash(
            {name: value for name, value in wrong_document.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, wrong_document, "SELF_HASH_MISMATCH")

        wrong_fixture_set = self._custom_registry()
        fixture = wrong_fixture_set["entries"][0]["canonical_fixture_set"]["minimal_valid"]
        fixture["required_label"] = "changed"
        wrong_fixture_set["entries"][0]["canonical_fixture_set"]["minimal_valid"] = self._seal(fixture, self._CUSTOM_SCHEMA)
        wrong_fixture_set["self_sha256"] = canonical_hash(
            {name: value for name, value in wrong_fixture_set.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, wrong_fixture_set, "FIXTURE_SET_HASH_MISMATCH")

        wrong_controls = self._custom_registry()
        wrong_controls["entries"][0]["mutation_controls"]["controls"][0]["mutation"]["path"] = "/other"
        wrong_controls["self_sha256"] = canonical_hash(
            {name: value for name, value in wrong_controls.items() if name != "self_sha256"},
            receipts.SCHEMA_REGISTRY_SCHEMA,
        )
        self._assert_rejected(receipt, wrong_controls, "MUTATION_CONTROLS_HASH_MISMATCH")


    def test_registered_object_builders_use_registry_fixtures(self) -> None:
        for schema in ("cassi.qi-flow-text-event.v2", "cassi.qi-flow-tick-intent.v1"):
            with self.subTest(schema=schema):
                entry = self._entry(schema)
                fixture = copy.deepcopy(entry["canonical_fixture_set"]["minimal_valid"])
                self_hash_field = entry["self_hash_field"]
                payload = {
                    name: value
                    for name, value in fixture.items()
                    if name not in {"schema", self_hash_field}
                }
                built = receipts.build_registered_object(schema, payload)
                self.assertEqual(built, fixture)
                self.assertEqual(
                    receipts.validate_registered_object(built, expected_schema=schema),
                    fixture,
                )
                encoded = canonical_json_bytes(fixture)
                self.assertEqual(
                    receipts.validate_registered_object(encoded, expected_schema=schema),
                    fixture,
                )

    def test_registered_object_rejects_unknown_and_receipt_classes(self) -> None:
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^OBJECT_CLASS_MISMATCH:"):
            receipts.build_registered_object("cassi.qi-flow-unknown.v1", {})
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^OBJECT_CLASS_MISMATCH:"):
            receipts.build_registered_object(receipts.RECEIPT_SCHEMAS["step"], {})

    def test_registered_object_enforces_shape_encoding_identity_and_root(self) -> None:
        schema = "cassi.qi-flow-text-event.v2"
        entry = self._entry(schema)
        fixture = copy.deepcopy(entry["canonical_fixture_set"]["minimal_valid"])
        self_hash_field = entry["self_hash_field"]

        unknown = copy.deepcopy(fixture)
        unknown["__extra__"] = "x"
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^UNKNOWN_KEY:"):
            receipts.validate_registered_object(unknown, expected_schema=schema)

        missing = copy.deepcopy(fixture)
        missing_name = next(
            name
            for name in entry["schema_document"]["required_keys"]
            if name not in {"schema", self_hash_field}
        )
        del missing[missing_name]
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^MISSING_REQUIRED_KEY:"):
            receipts.validate_registered_object(missing, expected_schema=schema)

        null_value = copy.deepcopy(fixture)
        null_name = next(
            name
            for name in entry["schema_document"]["required_keys"]
            if name not in {"schema", self_hash_field} | set(entry["schema_document"]["nullable_keys"])
        )
        null_value[null_name] = None
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^FORBIDDEN_NULL:"):
            receipts.validate_registered_object(null_value, expected_schema=schema)

        wrong_self = copy.deepcopy(fixture)
        wrong_self[self_hash_field] = "0" * 64
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^SELF_HASH_MISMATCH:"):
            receipts.validate_registered_object(wrong_self, expected_schema=schema)

        reordered = dict(reversed(tuple(fixture.items())))
        reordered_bytes = json.dumps(
            reordered,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^NONCANONICAL_ENCODING:"):
            receipts.validate_registered_object(reordered_bytes, expected_schema=schema)

        parent_schema = "cassi.qi-flow-antialias.v1"
        parent_fixture = copy.deepcopy(self._entry(parent_schema)["canonical_fixture_set"]["minimal_valid"])
        parent_fixture["consumed_semantic_subhashes"].reverse()
        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^SEMANTIC_PARENT_ORDER_MISMATCH:"):
            receipts.validate_registered_object(parent_fixture, expected_schema=parent_schema)

        with self.assertRaisesRegex(PROFILE_MISMATCH, r"^HASH_DOMAIN_MISMATCH:"):
            receipts.validate_registered_object(
                self._entry(parent_schema)["canonical_fixture_set"]["minimal_valid"],
                expected_schema=parent_schema,
                contract_root=self.root,
            )
if __name__ == "__main__":
    unittest.main()
