"""Seal the source-exact W3N/G3N periodic-FFT2 numerical certificate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Mapping

from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_numerical_certificate import (
    NUMERICAL_CERTIFICATE_DOMAIN,
    NUMERICAL_GUARD_DOMAIN,
    build_numerical_certificate,
    build_registry_extension,
    evaluate_online_guard,
)
from cassi_qi_profile import canonical_hash, canonical_json_bytes, finite_float, load_development_profile
from cassi_qi_transport import load_w3_transport_profile

ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w3n-periodic-fft2-final"
W1_ARTIFACT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w1-final"
W3_ARTIFACT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w3-periodic-fft2-final"
INDEX_SCHEMA = "cassi.qi-flow-w3n-periodic-fft2-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w3n-periodic-fft2-artifact.v1"
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w3n-periodic-fft2-source-identity.v1"
W3_ARTIFACT_IDENTITY_SCHEMA = "cassi.qi-flow-w3-artifact-identity.v1"
GUARD_REPLAY_SCHEMA = "cassi.qi-flow-w3n-guard-replay.v2"
CONTROLS_SCHEMA = "cassi.qi-flow-w3n-controls.v2"
CANDIDATE_SCHEMA = "cassi.qi-flow-g3n-candidate.v2"
STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
SOURCE_PATHS = tuple(sorted((
    "CassiFI/10-work-packages.md",
    "CassiFI/11-validation-gates.md",
    "cassi-qi-flow-development.json",
    "cassi_qi_field.py",
    "cassi_qi_geometry.py",
    "cassi_qi_numerical_certificate.py",
    "cassi_qi_profile.py",
    "cassi_qi_transport.py",
    "run_cassi_qi_numerical_certificate.py",
    "test_cassi_qi_numerical_certificate.py",
    "verify_cassi_qi_numerical_certificate.py",
    "verify_cassi_qi_transport.py",
), key=lambda value: value.encode("utf-8")))


class NumericalCertificateRunError(RuntimeError):
    pass


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise NumericalCertificateRunError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise NumericalCertificateRunError(f"{path} is not a JSON object")
    return value


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(root: Path, relative: str, value: Mapping[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(_plain(value)))


def _source_identity(stage: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        if not source.is_file():
            raise NumericalCertificateRunError(f"required source is missing: {relative}")
        raw = source.read_bytes()
        snapshot = stage / "sources" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        rows.append({"path": relative, "bytes": len(raw), "sha256": _sha(raw)})
    core = {"schema": SOURCE_IDENTITY_SCHEMA, "sources": rows}
    return {**core, "source_identity_sha256": canonical_hash(core, SOURCE_IDENTITY_SCHEMA)}


def _discover_w1(profile: Any) -> dict[str, str]:
    candidates: list[Path] = []
    if not W1_ARTIFACT_ROOT.is_dir():
        raise NumericalCertificateRunError("current W1 artifact root is missing")
    for directory in sorted(W1_ARTIFACT_ROOT.iterdir(), key=lambda path: path.name.encode("utf-8")):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        try:
            index = _load(directory / "index.json")
            identity = _load(directory / "run-spec" / "source-identity.json")
            sources = identity["sources"]
        except Exception:
            continue
        if index.get("profile_sha256") != profile.profile_sha256 or index.get("contract_root_sha256") != profile.contract_root_sha256:
            continue
        if not isinstance(sources, list) or not all(
            isinstance(row, Mapping)
            and isinstance(row.get("path"), str)
            and (ROOT / row["path"]).is_file()
            and _sha((ROOT / row["path"]).read_bytes()) == row.get("sha256")
            for row in sources
        ):
            continue
        candidates.append(directory)
    if len(candidates) != 1:
        raise NumericalCertificateRunError(f"expected one current source-exact W1 artifact, found {len(candidates)}")
    directory = candidates[0]
    index = _load(directory / "index.json")
    registry = _load(directory / "run-spec" / "schema-registry" / "manifest.json")
    return {
        "run_id": str(index["run_id"]),
        "index_sha256": _sha((directory / "index.json").read_bytes()),
        "profile_sha256": str(index["profile_sha256"]),
        "contract_root_sha256": str(index["contract_root_sha256"]),
        "schema_registry_sha256": str(registry["self_sha256"]),
    }


def _discover_w3(transport: Any) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    if not W3_ARTIFACT_ROOT.is_dir():
        raise NumericalCertificateRunError("corrected W3 artifact root is missing")
    for directory in sorted(W3_ARTIFACT_ROOT.iterdir(), key=lambda path: path.name.encode("utf-8")):
        if not directory.is_dir() or directory.name.startswith(".") or not (directory / "index.json").is_file():
            continue
        try:
            index = _load(directory / "index.json")
            identity = _load(directory / "run-spec" / "source-identity.json")
            sources = identity["sources"]
        except Exception:
            continue
        if (
            index.get("status") != "PASS_W3_G3"
            or index.get("profile_sha256") != transport.profile_sha256
            or index.get("contract_root_sha256") != transport.contract_root_sha256
            or index.get("semantic_sha256") != transport.transport_semantic_sha256
            or not isinstance(sources, list)
            or not all(
                isinstance(row, Mapping)
                and isinstance(row.get("path"), str)
                and (ROOT / row["path"]).is_file()
                and _sha((ROOT / row["path"]).read_bytes()) == row.get("sha256")
                for row in sources
            )
        ):
            continue
        matches.append({
            "schema": W3_ARTIFACT_IDENTITY_SCHEMA,
            "run_id": str(index["run_id"]),
            "index_sha256": _sha((directory / "index.json").read_bytes()),
            "profile_sha256": str(index["profile_sha256"]),
            "contract_root_sha256": str(index["contract_root_sha256"]),
            "semantic_sha256": str(index["semantic_sha256"]),
            "stage_schedule_sha256": str(index["stage_schedule_sha256"]),
            "source_identity_sha256": str(index["source_identity_sha256"]),
            "parent_w2_run_id": str(index["parent_w2_run_id"]),
            "parent_w2_profile_sha256": str(index["parent_w2_profile_sha256"]),
            "parent_w2_contract_root_sha256": str(index["parent_w2_contract_root_sha256"]),
        })
    if len(matches) != 1:
        raise NumericalCertificateRunError(f"expected one current source-exact W3 artifact, found {len(matches)}")
    return matches[0]


def _raw(shape_prefix: list[int], *, batch: int = 1, value: float = 0.0) -> bytes:
    raw = bytearray(math.prod([*shape_prefix, batch]) * 8)
    if raw:
        struct.pack_into("<d", raw, 0, value)
    return bytes(raw)


def _guard_replay(stage: Path, certificate: Mapping[str, Any]) -> dict[str, Any]:
    contract = certificate["online_guard_contract"]
    layout = contract["raw_layout"]
    shape_prefix = [int(value) for value in layout["shape_prefix"]]
    threshold = finite_float(contract["raw_component_admission_abs"], name="W3N raw admission")
    cases = (
        ("accepted", _raw(shape_prefix), None, None, None, "ACCEPT", "accepted"),
        ("exact-boundary", _raw(shape_prefix, value=threshold), None, None, None, "ACCEPT", "accepted"),
        ("just-above-boundary", _raw(shape_prefix, value=math.nextafter(threshold, math.inf)), None, None, None, "REJECT", "raw-component-envelope-exceeded"),
        ("dtype-mismatch", _raw(shape_prefix), "float32", None, None, "REJECT", "dtype-mismatch"),
        ("backend-mismatch", _raw(shape_prefix), None, "gpu", None, "REJECT", "backend-mismatch"),
        ("nonempty-source", _raw(shape_prefix), None, None, {"force": "f64:3f9eb851eb851eb8"}, "REJECT", "source-budget-exceeded"),
        ("nonfinite", _raw(shape_prefix, value=math.nan), None, None, None, "REJECT", "nonfinite-or-negative-zero-raw-state"),
        ("negative-zero", _raw(shape_prefix, value=-0.0), None, None, None, "REJECT", "nonfinite-or-negative-zero-raw-state"),
        ("raw-byte-mutation", _raw(shape_prefix, value=math.nextafter(0.0, 1.0)), None, None, None, "ACCEPT", "accepted"),
        ("malformed-layout", b"bad", None, None, None, "REJECT", "raw-layout-mismatch"),
        ("batch-limit", _raw(shape_prefix, batch=int(layout["batch_limit"]) + 1), None, None, None, "REJECT", "raw-layout-mismatch"),
    )
    rows: list[dict[str, Any]] = []
    for case_id, raw, dtype, backend, source, decision, reason in cases:
        relative = f"fixtures/{case_id}.f64le"
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        receipt = evaluate_online_guard(certificate, raw_state=raw, source=source, dtype=dtype, backend=backend)
        if receipt["decision"] != decision or receipt["reason"] != reason:
            raise NumericalCertificateRunError(f"guard case {case_id} disagrees with its frozen verdict")
        _write_json(stage, f"receipts/guard-{case_id}.json", receipt)
        rows.append({
            "id": case_id,
            "raw_path": relative,
            "raw_bytes": len(raw),
            "raw_sha256": _sha(raw),
            "dtype": dtype,
            "backend": backend,
            "source": source,
            "expected_decision": decision,
            "expected_reason": reason,
            "receipt_path": f"receipts/guard-{case_id}.json",
            "receipt_sha256": receipt["self_sha256"],
        })
    core = {"schema": GUARD_REPLAY_SCHEMA, "cases": rows}
    return {**core, "self_sha256": canonical_hash(core, GUARD_REPLAY_SCHEMA)}


def _controls(certificate: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, Any]:
    tampered = _plain(certificate)
    tampered["offline_derivation"]["precision"]["rounding"] = "nearest"
    certificate_identity_rejected = False
    try:
        evaluate_online_guard(tampered, raw_state=b"bad")
    except Exception:
        certificate_identity_rejected = True
    rows = {
        row["id"]: row["expected_decision"]
        for row in replay["cases"]
    }
    core = {
        "schema": CONTROLS_SCHEMA,
        "certificate_identity_rejected": certificate_identity_rejected,
        "exact_boundary_accepted": rows.get("exact-boundary") == "ACCEPT",
        "above_boundary_rejected": rows.get("just-above-boundary") == "REJECT",
        "dtype_rejected": rows.get("dtype-mismatch") == "REJECT",
        "backend_rejected": rows.get("backend-mismatch") == "REJECT",
        "source_rejected": rows.get("nonempty-source") == "REJECT",
        "nonfinite_rejected": rows.get("nonfinite") == "REJECT",
        "negative_zero_rejected": rows.get("negative-zero") == "REJECT",
        "layout_rejected": rows.get("malformed-layout") == "REJECT" and rows.get("batch-limit") == "REJECT",
        "raw_identity_changes_observed": rows.get("raw-byte-mutation") == "ACCEPT",
        "status": "PASS",
    }
    if not certificate_identity_rejected or any(value is False for key, value in core.items() if key not in {"schema", "status"}):
        raise NumericalCertificateRunError("W3N mutation controls failed")
    return {**core, "self_sha256": canonical_hash(core, CONTROLS_SCHEMA)}


def _objects(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((item for item in root.rglob("*") if item.is_file() and item.name != "index.json"), key=lambda item: item.relative_to(root).as_posix().encode("utf-8")):
        raw = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": _sha(raw)})
    return rows


def run(*, output_root: str | Path | None = None) -> dict[str, Any]:
    profile = load_development_profile()
    geometry = load_w2_geometry_profile(base_profile=profile)
    transport = load_w3_transport_profile(geometry=geometry)
    w1_identity = _discover_w1(profile)
    w3_identity = _discover_w3(transport)
    certificate, extension = build_numerical_certificate(
        geometry=geometry,
        transport=transport,
        accepted_w3_artifact_identity=w3_identity,
    )
    registry = build_registry_extension(
        parent_registry_sha256=w1_identity["schema_registry_sha256"],
        parent_w1_run_id=w1_identity["run_id"],
    )
    root = Path(output_root).resolve() if output_root is not None else ARTIFACT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w3n-", dir=root))
    try:
        source_identity = _source_identity(stage)
        replay = _guard_replay(stage, certificate)
        controls = _controls(certificate, replay)
        _write_json(stage, "certificate/certificate-root.json", certificate)
        _write_json(stage, "certificate/extension-0001.json", extension)
        _write_json(stage, "certificate/schema-registry-extension.json", registry)
        _write_json(stage, "run-spec/accepted-w1.json", w1_identity)
        _write_json(stage, "run-spec/accepted-w3.json", w3_identity)
        _write_json(stage, "run-spec/source-identity.json", source_identity)
        _write_json(stage, "gates/g03n-numerical-certificate/guard-replay.json", replay)
        _write_json(stage, "gates/g03n-numerical-certificate/controls.json", controls)
        candidate_core = {
            "schema": CANDIDATE_SCHEMA,
            "status": "PASS_W3N_G3N",
            "numerical_certificate_sha256": certificate["self_sha256"],
            "certificate_extension_sha256": extension["self_sha256"],
            "registry_extension_sha256": registry["self_sha256"],
            "guard_replay_sha256": replay["self_sha256"],
            "controls_sha256": controls["self_sha256"],
            "complete_section_inventory": extension["complete_section_inventory"],
        }
        candidate = {**candidate_core, "self_sha256": canonical_hash(candidate_core, CANDIDATE_SCHEMA)}
        _write_json(stage, "gates/g03n-numerical-certificate/certificate.json", candidate)
        status = {
            "schema": STATUS_SCHEMA,
            "gate": "G3N",
            "status": "PASS",
            "certificate_sha256": certificate["self_sha256"],
            "candidate_sha256": candidate["self_sha256"],
            "accepted_w3_run_id": w3_identity["run_id"],
            "source_identity_sha256": source_identity["source_identity_sha256"],
        }
        _write_json(stage, "gates/g03n-numerical-certificate/status.json", status)
        index_core = {
            "schema": INDEX_SCHEMA,
            "status": "PASS_W3N_G3N",
            "parents": {"w1": w1_identity, "w2": _plain(certificate["w2_parent"]), "w3": w3_identity},
            "profile_sha256": transport.profile_sha256,
            "contract_root_sha256": transport.contract_root_sha256,
            "transport_semantic_sha256": transport.transport_semantic_sha256,
            "execution_schedule_sha256": certificate["execution_schedule_sha256"],
            "numerical_certificate_sha256": certificate["self_sha256"],
            "certificate_extension_sha256": extension["self_sha256"],
            "registry_extension_sha256": registry["self_sha256"],
            "candidate_sha256": candidate["self_sha256"],
            "source_identity_sha256": source_identity["source_identity_sha256"],
            "objects": _objects(stage),
        }
        run_id = canonical_hash(index_core, ARTIFACT_DOMAIN)
        without_self = {**index_core, "run_id": run_id}
        index = {**without_self, "self_sha256": canonical_hash(without_self, INDEX_SCHEMA)}
        _write_json(stage, "index.json", index)

        from verify_cassi_qi_numerical_certificate import verify_artifact

        destination = root / run_id
        if destination.exists():
            verification = verify_artifact(destination)
            shutil.rmtree(stage)
        else:
            verification = verify_artifact(stage)
            if verification.get("status") != "PASS_W3N_G3N":
                raise NumericalCertificateRunError("independent W3N verification did not pass")
            stage.replace(destination)
        return {
            "status": "PASS_W3N_G3N",
            "artifact": destination.relative_to(ROOT).as_posix(),
            "run_id": run_id,
            "numerical_certificate_sha256": certificate["self_sha256"],
            "verification": verification,
        }
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
def run_artifact(*, output_root: str | Path | None = None) -> Path:
    """Workflow entry point returning the sealed artifact directory."""
    return ROOT / run(output_root=output_root)["artifact"]




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = run(output_root=args.output_root)
    if args.json:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(f"PASS_W3N_G3N {result['artifact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
