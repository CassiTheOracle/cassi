from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

import verify_cassi_qi_flow as independent


_ROOT = Path(__file__).resolve().parent
_W1_PARENT = {
    "kind": "sealed-w1-g1",
    "run_id": "0b32868325822dc50a1e4226b5ada4ce8e1447920561f3feeaa8b8d7e68c3087",
    "path": "_diag/cassi-qi-flow-w1-final/0b32868325822dc50a1e4226b5ada4ce8e1447920561f3feeaa8b8d7e68c3087",
    "index_sha256": "f2dce7ab4005aae2e0a99542f7fc1eb7abe616f844091b48a5e0adcee58708f1",
    "contract_root_sha256": "1ba6e94fb3f996989dd770c61670aceda0e2b1c3049368c79a084e458e6acaab",
    "profile_sha256": "ff29e3b4c2c3315000d80e5f97c68e2bcbce5aa511f61d41814b8bf01753e3df",
}
_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.w2"
_ROOT_SCHEMA = "cassi.qi-flow-contract-root.w2"
_PROFILE_SCHEMA = "cassi.qi-flow-geometry-profile.w2"
_GEOMETRY_SCHEMA = "cassi.qi-flow-periodic-sheet.w2"
_OPERATOR_SCHEMA = "cassi.qi-flow-geometry-operators.w2"
_PARENT_LINK_SCHEMA = "cassi.qi-flow-parent-link.w2"
_SOURCE_SCHEMA = "cassi.qi-flow-source-identity.w2"
_CANDIDATE_SCHEMA = "cassi.qi-flow-g2-geometry-candidate.v1"
_STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
_ARTIFACT_SCHEMA = "cassi.qi-flow-w2-artifact.v1"
_ZERO = "f64:0000000000000000"
_TOLERANCE = "f64:3d719799812dea11"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def _canonical_hash(value: Any, domain: str) -> str:
    return hashlib.sha256(
        _frame(domain.encode("utf-8")) + _frame(_canonical_bytes(value))
    ).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> dict[str, Any]:
    specifications = {
        _ROOT_SCHEMA: (65536, []),
        _PROFILE_SCHEMA: (65536, ["geometry_contract_sha256", "operator_semantic_sha256"]),
        _GEOMETRY_SCHEMA: (65536, []),
        _OPERATOR_SCHEMA: (65536, ["geometry_contract_sha256"]),
        _PARENT_LINK_SCHEMA: (65536, []),
        _SOURCE_SCHEMA: (65536, []),
        _CANDIDATE_SCHEMA: (262144, ["geometry_contract_sha256", "operator_semantic_sha256"]),
        _STATUS_SCHEMA: (65536, ["geometry_contract_sha256", "operator_semantic_sha256"]),
        _INDEX_SCHEMA: (1048576, []),
    }
    return {
        "schema": _REGISTRY_SCHEMA,
        "entries": [
            {
                "schema": schema,
                "max_bytes": maximum,
                "semantic_parents": parents,
            }
            for schema, (maximum, parents) in sorted(specifications.items())
        ],
    }


def _geometry() -> dict[str, Any]:
    return {
        "schema": _GEOMETRY_SCHEMA,
        "axis_order": ["Z", "Y", "X"],
        "grid_shape": [2, 4, 4],
        "mode_count": 32,
        "flattening": {
            "formula": "m=((z*Y)+y)*X+x",
            "axis_order": "Z,Y,X",
            "storage": "[M,B]<->[Z,Y,X,B]",
        },
        "units": {
            "coordinate": "m",
            "gradient": "m^-1",
            "laplacian": "m^-2",
        },
        "boundary_condition": "periodic",
        "domain_lengths_m": [
            "f64:3f60624dd2f1a9fc",
            "f64:3f70624dd2f1a9fc",
            "f64:3f80624dd2f1a9fc",
        ],
        "spacings_m": [
            "f64:3f50624dd2f1a9fc",
            "f64:3f50624dd2f1a9fc",
            "f64:3f60624dd2f1a9fc",
        ],
        "coordinate_origin_m": [_ZERO, _ZERO, _ZERO],
        "nyquist": {
            "even_grid_first_derivative": "zero-centered-symbol",
            "second_difference": "-4/h^2",
        },
        "differential": {
            "gradient": "centered-periodic-roll",
            "divergence": "sum_axis_first_derivatives",
            "curl": "right-handed-[z,y,x]",
            "laplacian": "Dzz+Dyy+Dxx",
            "delta_perp": "Dyy+Dxx",
            "delta_s": "Dzz",
            "delta_identity": "Delta=Delta_perp+Delta_s",
            "first_adjoint": "D_axis^*=-D_axis",
            "laplacian_adjoint": "Delta_axis^*=Delta_axis",
        },
        "workspace_byte_cap": 65536,
    }


def _measurement(*names: str) -> dict[str, str]:
    return {**{name: _ZERO for name in names}, "tolerance": _TOLERANCE}


def _seal_index(root: Path) -> None:
    root_record = _load_json(root / "run-spec" / "w2-contract-root.json")
    profile = _load_json(root / "run-spec" / "w2-profile.json")
    parent_link = _load_json(root / "run-spec" / "parent-link.json")
    objects = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.relative_to(root).as_posix() == "index.json":
            continue
        raw = path.read_bytes()
        objects.append(
            {
                "path": path.relative_to(root).as_posix(),
                "byte_count": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    material = {
        "schema": _ARTIFACT_SCHEMA,
        "parents": parent_link["parents"],
        "objects": objects,
        "contract_root_sha256": root_record["self_sha256"],
        "profile_sha256": profile["profile_sha256"],
    }
    index = {
        "schema": _INDEX_SCHEMA,
        "run_id": _canonical_hash(material, _ARTIFACT_SCHEMA),
        "status": "PASS_W2_G2",
        "parents": parent_link["parents"],
        "contract_root_sha256": root_record["self_sha256"],
        "profile_sha256": profile["profile_sha256"],
        "object_count": len(objects),
        "objects": objects,
    }
    index["self_sha256"] = _canonical_hash(index, _INDEX_SCHEMA)
    _write_json(root / "index.json", index)


def _build_w2_artifact(root: Path) -> None:
    registry = _registry()
    geometry = _geometry()
    geometry_sha256 = _canonical_hash(geometry, _GEOMETRY_SCHEMA)
    operator = {
        "schema": _OPERATOR_SCHEMA,
        "geometry_contract_sha256": geometry_sha256,
        "dtype": "float64",
        "device": "cpu",
        "inner_product": "sum(conj(a)*b)*dz*dy*dx",
        "gradient": "centered-periodic-roll",
        "divergence": "sum_axis_first_derivatives",
        "curl": "right-handed-[z,y,x]",
        "laplacian": "Dzz+Dyy+Dxx",
        "delta_perp_identity": "Delta_perp=Dyy+Dxx",
        "delta_s_identity": "Delta_s=Dzz",
        "nyquist": dict(geometry["nyquist"]),
    }
    operator_sha256 = _canonical_hash(operator, _OPERATOR_SCHEMA)
    root_without_self = {
        "schema": _ROOT_SCHEMA,
        "contract_root_id": "qi-flow-geometry-w2-development-v1",
        "parent_w1": dict(_W1_PARENT),
        "base_profile_sha256": _W1_PARENT["profile_sha256"],
        "base_contract_root_sha256": _W1_PARENT["contract_root_sha256"],
        "schema_registry": {
            "schema": _REGISTRY_SCHEMA,
            "sha256": _canonical_hash(registry, _REGISTRY_SCHEMA),
        },
        "geometry_contract": {"schema": _GEOMETRY_SCHEMA, "sha256": geometry_sha256},
        "operator_semantic": {"schema": _OPERATOR_SCHEMA, "sha256": operator_sha256},
    }
    root_record = {
        **root_without_self,
        "self_sha256": _canonical_hash(root_without_self, _ROOT_SCHEMA),
    }
    profile_without_hash = {
        "schema": _PROFILE_SCHEMA,
        "parent_w1": dict(_W1_PARENT),
        "base_profile_sha256": _W1_PARENT["profile_sha256"],
        "base_contract_root_sha256": _W1_PARENT["contract_root_sha256"],
        "schema_registry_sha256": _canonical_hash(registry, _REGISTRY_SCHEMA),
        "geometry_contract": geometry,
        "geometry_contract_sha256": geometry_sha256,
        "operator_semantic": operator,
        "operator_semantic_sha256": operator_sha256,
        "contract_root_sha256": root_record["self_sha256"],
    }
    profile = {
        **profile_without_hash,
        "profile_sha256": _canonical_hash(profile_without_hash, _PROFILE_SCHEMA),
    }
    metadata = {
        "geometry_profile_sha256": profile["profile_sha256"],
        "geometry_contract_root_sha256": root_record["self_sha256"],
        "geometry_contract_sha256": geometry_sha256,
        "operator_semantic_sha256": operator_sha256,
        "grid_shape": [2, 4, 4],
        "mode_count": 32,
        "axis_order": ["Z", "Y", "X"],
        "domain_lengths_m": list(geometry["domain_lengths_m"]),
        "spacings_m": list(geometry["spacings_m"]),
        "units": dict(geometry["units"]),
        "nyquist": dict(geometry["nyquist"]),
        "differential": dict(geometry["differential"]),
        "workspace_byte_cap": 65536,
    }
    manufactured = {
        name: _measurement("gradient_max_abs_error", "laplacian_max_abs_error")
        for name in (
            "constant",
            "linear",
            "quadratic",
            "sinusoid",
            "mixed_frequency",
            "nyquist",
        )
    }
    candidate_without_self = {
        "schema": _CANDIDATE_SCHEMA,
        "parent_w1": dict(_W1_PARENT),
        "geometry_profile_sha256": profile["profile_sha256"],
        "geometry_contract_root_sha256": root_record["self_sha256"],
        "geometry_contract_sha256": geometry_sha256,
        "operator_semantic_sha256": operator_sha256,
        "grid_shape": [2, 4, 4],
        "dtype": "float64",
        "device": "cpu",
        "operator_metadata": metadata,
        "manufactured": manufactured,
        "adjoint": _measurement(
            "derivative_inner_product_residual",
            "laplacian_inner_product_residual",
        ),
        "skew_adjoint": _measurement("z_residual", "y_residual", "x_residual"),
        "delta_identity": {
            **_measurement("max_abs_error"),
            "delta_perp": "Dyy+Dxx",
            "delta_s": "Dzz",
        },
        "flatten_direct_index_error": _measurement("max_abs_error"),
        "flatten_batched_reference_error": _measurement("max_abs_error"),
        "coordinate_lane_order": {
            **_measurement("max_abs_error"),
            "coordinate_origin_m": [_ZERO, _ZERO, _ZERO],
            "lane_order": "[M,B]",
        },
        "workspace": {
            "workspace_byte_cap": 65536,
            "scalar_batch4_estimate_bytes": 1024,
            "vector_batch4_estimate_bytes": 2048,
        },
        "mutation_controls": {
            "coordinate_contract_mutation_rejected": True,
            "lane_order_mutation_rejected": True,
            "operator_semantic_mutation_rejected": True,
            "memory_cap_mutation_rejected": True,
            "predecessor_unchanged": True,
        },
    }
    candidate = {
        **candidate_without_self,
        "self_sha256": _canonical_hash(candidate_without_self, _CANDIDATE_SCHEMA),
    }
    status = {
        "schema": _STATUS_SCHEMA,
        "gate": "G2",
        "status": "PASS",
        "geometry_profile_sha256": profile["profile_sha256"],
        "geometry_contract_root_sha256": root_record["self_sha256"],
        "geometry_contract_sha256": geometry_sha256,
        "operator_semantic_sha256": operator_sha256,
        "candidate_sha256": candidate["self_sha256"],
        "registered_schema_count": 9,
        "workspace_peak_bytes": 2048,
    }
    source_bytes = {
        "cassi-qi-flow-development.json": b'{"synthetic":"w2"}\n',
        "cassi_qi_field.py": b"synthetic field source\n",
        "cassi_qi_geometry.py": b"synthetic geometry source\n",
        "cassi_qi_profile.py": b"synthetic profile source\n",
        "run_cassi_qi_geometry.py": b"synthetic geometry runner\n",
        "verify_cassi_qi_flow.py": b"synthetic independent verifier source\n",
    }
    source_records = [
        {"path": relative, "sha256": hashlib.sha256(payload).hexdigest()}
        for relative, payload in sorted(source_bytes.items())
    ]
    for relative, payload in source_bytes.items():
        source_path = root / "run-spec" / "sources" / relative
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(payload)
    _write_json(root / "run-spec" / "w2-schema-registry.json", registry)
    _write_json(root / "run-spec" / "w2-geometry-contract.json", geometry)
    _write_json(root / "run-spec" / "w2-operator-contract.json", operator)
    _write_json(root / "run-spec" / "w2-contract-root.json", root_record)
    _write_json(root / "run-spec" / "w2-profile.json", profile)
    _write_json(
        root / "run-spec" / "parent-link.json",
        {"schema": _PARENT_LINK_SCHEMA, "parents": [dict(_W1_PARENT)]},
    )
    _write_json(
        root / "run-spec" / "source-identity.json",
        {"schema": _SOURCE_SCHEMA, "sources": source_records},
    )
    _write_json(root / "gates" / "g02-geometry" / "geometry.json", candidate)
    _write_json(root / "gates" / "g02-geometry" / "status.json", status)
    _seal_index(root)


def _reseal_candidate(root: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    candidate_path = root / "gates" / "g02-geometry" / "geometry.json"
    candidate = _load_json(candidate_path)
    mutation(candidate)
    candidate_without_self = dict(candidate)
    candidate_without_self.pop("self_sha256")
    candidate["self_sha256"] = _canonical_hash(candidate_without_self, _CANDIDATE_SCHEMA)
    _write_json(candidate_path, candidate)
    status_path = root / "gates" / "g02-geometry" / "status.json"
    status = _load_json(status_path)
    status["candidate_sha256"] = candidate["self_sha256"]
    _write_json(status_path, status)
    _seal_index(root)


class IndependentG2VerifierTests(unittest.TestCase):
    def _artifact(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "synthetic-w2"
        _build_w2_artifact(root)
        return temporary, root

    def test_synthetic_w2_artifact_passes_and_cli_dispatches_g2(self) -> None:
        temporary, root = self._artifact()
        with temporary:
            result = independent.verify_g2_geometry(root)
            self.assertEqual(result["gate"], "G2")
            self.assertEqual(result["status"], "PASS")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(_ROOT / "verify_cassi_qi_flow.py"),
                    "--run-root",
                    str(root),
                ],
                cwd=_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["gate"], "G2")

    def test_resealed_coordinate_contract_mutation_is_rejected(self) -> None:
        temporary, root = self._artifact()
        with temporary:
            _reseal_candidate(
                root,
                lambda candidate: candidate["coordinate_lane_order"]["coordinate_origin_m"].__setitem__(
                    0,
                    "f64:3f50624dd2f1a9fc",
                ),
            )
            with self.assertRaises(independent.VerificationError):
                independent.verify_g2_geometry(root)

    def test_resealed_lane_order_mutation_is_rejected(self) -> None:
        temporary, root = self._artifact()
        with temporary:
            _reseal_candidate(
                root,
                lambda candidate: candidate["coordinate_lane_order"].__setitem__(
                    "lane_order",
                    "[B,M]",
                ),
            )
            with self.assertRaises(independent.VerificationError):
                independent.verify_g2_geometry(root)

    def test_resealed_mutation_control_failure_is_rejected(self) -> None:
        temporary, root = self._artifact()
        with temporary:
            _reseal_candidate(
                root,
                lambda candidate: candidate["mutation_controls"].__setitem__(
                    "predecessor_unchanged",
                    False,
                ),
            )
            with self.assertRaises(independent.VerificationError):
                independent.verify_g2_geometry(root)

    def test_index_digest_mutation_is_rejected(self) -> None:
        temporary, root = self._artifact()
        with temporary:
            index_path = root / "index.json"
            index = _load_json(index_path)
            index["objects"][0]["sha256"] = "0" * 64
            _write_json(index_path, index)
            with self.assertRaises(independent.VerificationError):
                independent.verify_g2_geometry(root)

    def test_reordered_contract_map_is_rejected_before_pass(self) -> None:
        temporary, root = self._artifact()
        with temporary:
            root_path = root / "run-spec" / "w2-contract-root.json"
            root_record = _load_json(root_path)
            reordered = {key: root_record[key] for key in reversed(tuple(root_record))}
            root_path.write_bytes(
                json.dumps(
                    reordered,
                    ensure_ascii=False,
                    sort_keys=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
            with self.assertRaises(independent.VerificationError):
                independent.verify_g2_geometry(root)


if __name__ == "__main__":
    unittest.main()
