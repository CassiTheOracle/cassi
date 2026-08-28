from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cassi_qi_bootstrap import CanonicalCodecError, MAX_CANONICAL_BYTES
from cassi_qi_profile import canonical_json_bytes
from verify_cassi_qi_carrier import (
    CONTROL_IDS,
    CarrierVerificationError,
    _carrier_transform_phi,
    _control_result_path,
    _load_indexed_control_result,
    _root_name_allowed,
    _w3n_verification_passed,
)


class CompactControlIndexTests(unittest.TestCase):
    def test_compact_index_loads_canonical_detail_and_stays_below_budget(self) -> None:
        detail = {
            "schema": "cassi.qi-flow-w4-periodic-fft2-control.v1",
            "name": "D+C",
            "batch_lanes": 1,
            "evidence": "x" * 25_000,
        }
        raw = canonical_json_bytes(detail)
        relative = _control_result_path("D+C", 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            loaded, loaded_path = _load_indexed_control_result(
                root,
                "D+C",
                1,
                {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()},
            )
        self.assertEqual(loaded, detail)
        self.assertEqual(loaded_path, relative)

        compact = {
            name: {
                "schema": "cassi.qi-flow-w4-periodic-fft2-control.v1",
                "name": name,
                "batch_lanes": [1, 2, 3, 4],
                "potential_enabled": name != "potential-off",
                "batch_index": {
                    str(batch): {
                        "path": _control_result_path(name, batch),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                    for batch in range(1, 5)
                },
            }
            for name in CONTROL_IDS
        }
        self.assertLess(len(canonical_json_bytes(compact)), MAX_CANONICAL_BYTES)
        expanded = {
            name: {
                "schema": "cassi.qi-flow-w4-periodic-fft2-control.v1",
                "name": name,
                "batch_lanes": [1, 2, 3, 4],
                "potential_enabled": name != "potential-off",
                "batches": {str(batch): detail for batch in range(1, 5)},
            }
            for name in CONTROL_IDS
        }
        with self.assertRaises(CanonicalCodecError):
            canonical_json_bytes(expanded)
    def test_staging_name_requires_explicit_preseal_mode(self) -> None:
        run_id = "a" * 64
        staging = ".w4-periodic-fft2-abcdef"
        self.assertFalse(_root_name_allowed(staging, run_id, allow_staging_root=False))
        self.assertTrue(_root_name_allowed(staging, run_id, allow_staging_root=True))
        self.assertFalse(_root_name_allowed(".w4-periodic-fft2-", run_id, allow_staging_root=True))
    def test_w3n_parent_requires_canonical_pass_status(self) -> None:
        self.assertTrue(_w3n_verification_passed({"status": "PASS_W3N_G3N"}))
        self.assertFalse(_w3n_verification_passed({"status": "PASS"}))
        self.assertFalse(_w3n_verification_passed({"status": "PASS_W3N_G3N_WRONG"}))
    def test_w3n_w2_identity_is_preserved_exactly(self) -> None:
        import run_cassi_qi_carrier as producer

        root = producer.ROOT / "_diag" / "cassi-qi-flow-w3n-periodic-fft2-final"
        matches = []
        for candidate in root.iterdir():
            if not candidate.is_dir() or not (candidate / "index.json").is_file():
                continue
            index = producer._read_json(candidate / "index.json")
            identity = producer._read_json(candidate / "run-spec" / "source-identity.json")
            rows = identity.get("sources", [])
            if (
                index.get("status") == "PASS_W3N_G3N"
                and candidate.name == index.get("run_id")
                and all(
                    isinstance(row, dict)
                    and (candidate / "sources" / row["path"]).read_bytes() == (producer.ROOT / row["path"]).read_bytes()
                    for row in rows
                )
            ):
                matches.append((candidate, index))
        self.assertEqual(len(matches), 1)
        candidate, index = matches[0]
        parents = index["parents"]
        canonical_w2 = parents["w2"]
        chain = producer._load_parent_chain(
            candidate,
            {"w3_identity": parents["w3"], "w2_identity": canonical_w2},
        )
        self.assertEqual(set(canonical_w2), {
            "contract_root_sha256",
            "family",
            "geometry_contract_sha256",
            "kind",
            "operator_semantic_sha256",
            "profile_sha256",
            "schema",
        })
        self.assertEqual(chain["w2_identity"], canonical_w2)
        self.assertEqual(chain["w2_run_id"], parents["w3"]["parent_w2_run_id"])
    def test_carrier_phi_rejects_profile_field_mutations(self) -> None:
        import copy

        from cassi_qi_profile import canonical_json_loads

        profile_paths = sorted(
            (Path(__file__).resolve().parent / "_diag" / "cassi-qi-flow-w4-periodic-fft2-final").glob(
                ".w4-periodic-fft2-*/profile/carrier-profile.json"
            )
        )
        self.assertTrue(profile_paths)
        profile = canonical_json_loads(profile_paths[0].read_bytes())
        transform = profile["d_c_transform"]
        self.assertGreater(_carrier_transform_phi(transform), 0.0)

        missing = dict(transform)
        missing.pop("phi")
        with self.assertRaises(CarrierVerificationError):
            _carrier_transform_phi(missing)

        extra = dict(transform)
        extra["unexpected"] = True
        with self.assertRaises(CarrierVerificationError):
            _carrier_transform_phi(extra)

        nonfinite = dict(transform)
        nonfinite["phi"] = "f64:7ff0000000000000"
        with self.assertRaises(CarrierVerificationError):
            _carrier_transform_phi(nonfinite)

        wrong_nested = copy.deepcopy(transform)
        wrong_nested["forward"]["D"] = "EY+phi*EI"
        with self.assertRaises(CarrierVerificationError):
            _carrier_transform_phi(wrong_nested)


if __name__ == "__main__":
    unittest.main()
