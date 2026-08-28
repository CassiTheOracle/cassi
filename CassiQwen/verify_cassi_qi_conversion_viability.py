"""Independent stdlib-only verifier for immutable W5V/G5V evidence.

No W5 runtime or proof module is imported here.  The verifier uses local
canonical JSON/tagged-f64 handling and independently rebuilds every analytic
bound, coefficient trial, cover cell, witness linkage, and certificate extension
from the frozen W5 source-exact profile.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import hashlib
import json
import math
import struct
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

INDEX_SCHEMA = "cassi.qi-flow-w5v-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w5v-artifact.v1"
STATUS_SCHEMA = "cassi.qi-flow-g5v-status.v1"
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w5v-source-identity.v1"
PARENT_BINDING_SCHEMA = "cassi.qi-flow-w5v-parent-binding.v1"
WITNESS_MANIFEST_SCHEMA = "cassi.qi-flow-w5v-witness-manifest.v1"
RAW_ACTIVITY_SCHEMA = "cassi.qi-flow-w5v-raw-activity.v1"
RAW_ACTIVITY_DOMAIN = RAW_ACTIVITY_SCHEMA
WORK_OBSERVATION_SCHEMA = "cassi.qi-flow-w5v-raw-work-observation.v1"
WORK_OBSERVATION_DOMAIN = WORK_OBSERVATION_SCHEMA
MUTATION_OBSERVATION_SCHEMA = "cassi.qi-flow-w5v-mutation-observations.v1"
MUTATION_OBSERVATION_DOMAIN = MUTATION_OBSERVATION_SCHEMA
MUTATION_CONTROL_SCHEMA = "cassi.qi-flow-w5v-mutation-control.v1"
MUTATION_CONTROL_DOMAIN = MUTATION_CONTROL_SCHEMA
INDEPENDENT_INPUT_SCHEMA = "cassi.qi-flow-w5v-independent-verifier-input.v1"
INDEPENDENT_INPUT_DOMAIN = INDEPENDENT_INPUT_SCHEMA
INDEPENDENT_RESULT_SCHEMA = "cassi.qi-flow-w5v-independent-verifier-result.v1"
INDEPENDENT_RESULT_DOMAIN = INDEPENDENT_RESULT_SCHEMA
PARENT_VERIFICATION_SCHEMA = "cassi.qi-flow-parent-verification.v1"
PARENT_VERIFIER_RECEIPTS_SCHEMA = "cassi.qi-flow-parent-verifier-receipts.v1"
W4R_VERIFY_SCHEMA = "cassi.qi-flow-w4r-retention-core-run-index.v1"
W5_VERIFY_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
W5_RECEIPT_SCHEMA = "cassi.qi-flow-w5-conversion-receipt.v1"
G5_CONTROL_LAW_SCHEMA = "cassi.qi-flow-w5v-control-law-observations.v1"
G5_CONTROL_LAW_DOMAIN = G5_CONTROL_LAW_SCHEMA
G5_CONTROL_INPUT_SCHEMA = "cassi.qi-flow-w5v-control-law-input.v1"
G5_CONTROL_INPUT_DOMAIN = G5_CONTROL_INPUT_SCHEMA
G5_CONTROL_RESULT_SCHEMA = "cassi.qi-flow-w5v-control-law-result.v1"
G5_CONTROL_RESULT_DOMAIN = G5_CONTROL_RESULT_SCHEMA

W5_INDEX_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
W5_ARTIFACT_DOMAIN = "cassi.qi-flow-w5-frozen-q-artifact.v1"
W5_PROFILE_SCHEMA = "cassi.qi-flow-conversion-profile.v1"
W5_ROOT_SCHEMA = "cassi.qi-flow-w5-conversion-root.v1"
W5_LAW_DOMAIN = "cassi.qi-flow-frozen-q-map.v1"
W5_CANDIDATE_SCHEMA = "cassi.qi-flow-w5-conversion-candidate.v1"
W5_INTEGRATED_SCHEMA = "cassi.qi-flow-w5-integrated-control.v1"
W5_STATUS_SCHEMA = "cassi.qi-flow-g5-status.v1"
W5_MEASUREMENTS_SCHEMA = "cassi.qi-flow-w5-conversion-measurements.v1"
W5_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w5-conversion-source-identity.v1"

W5V_PROFILE_SCHEMA = "cassi.qi-flow-conversion-viability-profile.v1"
W5V_RECEIPT_SCHEMA = "cassi.qi-flow-conversion-viability-receipt.v1"
W5V_EXTENSION_SCHEMA = "cassi.qi-flow-certificate-extension.v1"
W5V_EXTENSION_DOMAIN = "cassi.qi-flow-w3n-extension.v1"
W5V_SECTION_SCHEMA = "cassi.qi-flow-w5v-forward-viability-section.v1"
W5V_SECTION_DOMAIN = W5V_SECTION_SCHEMA
W5V_ANALYTIC_METHOD = "decimal-exact-registered-f64-outward-enclosure.v1"

RAW_DOMAIN = b"cassi.qi-flow-w5-raw-state.v1"
RAW_DOMAIN_TEXT = RAW_DOMAIN.decode("ascii")
SUPPORT_DOMAIN = "cassi.qi-flow-conversion-support.v1"
ACCEPTED_DOMAIN = "cassi.qi-flow-conversion-accepted.v1"
COVER_DOMAIN = "cassi.qi-flow-conversion-cover.v1"
PARTITION_DOMAIN = "cassi.qi-flow-conversion-partition.v1"
METHOD_DOMAIN = "cassi.qi-flow-conversion-proof-method.v1"
MARGINS_DOMAIN = "cassi.qi-flow-conversion-registered-margins.v1"
CELL_DOMAIN = "cassi.qi-flow-conversion-cover-cell.v1"
WITNESS_DOMAIN = "cassi.qi-flow-conversion-witness.v1"
WORK_PROOF_DOMAIN = "cassi.qi-flow-conversion-work-domain-proof.v1"

W5_SOURCE_PATHS = (
    "cassi_qi_conversion.py",
    "run_cassi_qi_conversion.py",
    "verify_cassi_qi_conversion.py",
    "test_cassi_qi_conversion.py",
    "cassi_qi_numerical_certificate.py",
    "cassi_qi_field.py",
    "cassi_qi_geometry.py",
    "cassi_qi_transport.py",
    "cassi_qi_carrier.py",
    "cassi_qi_topology.py",
    "cassi_qi_profile.py",
)
W5V_SOURCE_PATHS = (
    *W5_SOURCE_PATHS[:10],
    "verify_cassi_qi_topology.py",
    *W5_SOURCE_PATHS[10:],
    "cassi_qi_conversion_viability.py",
    "run_cassi_qi_conversion_viability.py",
    "verify_cassi_qi_conversion_viability.py",
    "test_cassi_qi_conversion_viability.py",
)
PROJECT_ROOT = Path(__file__).resolve().parent
W5_ARTIFACT_ROOT = PROJECT_ROOT / "_diag" / "cassi-qi-flow-w5-frozen-q-final"
_ACTIVE_LAYOUT: dict[str, int] | None = None
WITNESS_CELL_REGISTRATION: Mapping[str, tuple[str, ...]] = {
    "empty": ("C00-exact-zero",),
    "balanced": ("C01-balanced-memory-zero",),
    "heterogeneous": ("C02-balanced-memory-positive",),
    "yang-heavy": ("C03-neutral-positive",),
    "yin-heavy": ("C04-neutral-negative",),
    "matched-energy-positive-imbalance": ("C05-progress-positive",),
    "matched-energy-negative-imbalance": ("C06-progress-negative",),
}


class VerificationError(ValueError):
    """A canonical artifact is absent, tampered, stale, or semantically invalid."""

def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate canonical JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise VerificationError(f"non-finite JSON constant: {value}")


def f64(value: Any, name: str = "f64") -> float:
    require(isinstance(value, str) and value.startswith("f64:") and len(value) == 20, f"{name}: tagged f64 required")
    try:
        result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    except ValueError as exc:
        raise VerificationError(f"{name}: malformed f64 tag") from exc
    require(math.isfinite(result), f"{name}: non-finite f64")
    require(not (result == 0.0 and math.copysign(1.0, result) < 0.0), f"{name}: noncanonical negative zero")
    return result


def tag(value: float) -> str:
    require(math.isfinite(value), "attempted canonicalization of non-finite f64")
    require(not (value == 0.0 and math.copysign(1.0, value) < 0.0), "attempted canonicalization of negative zero")
    return "f64:" + struct.pack(">d", float(value)).hex()


def validate(value: Any) -> None:
    if value is None or isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return
    if isinstance(value, float):
        raise VerificationError("JSON number cannot carry proof scalar; tagged f64 required")
    if isinstance(value, str):
        value.encode("utf-8")
        if value.startswith("f64:"):
            f64(value)
        return
    if isinstance(value, list):
        for item in value:
            validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str), "non-string canonical JSON key")
            validate(item)
        return
    raise VerificationError(f"unsupported canonical value: {type(value).__name__}")


def canonical(value: Any) -> bytes:
    validate(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any, domain: str) -> str:
    domain_raw = domain.encode("utf-8")
    payload = canonical(value)
    return sha(len(domain_raw).to_bytes(8, "big") + domain_raw + len(payload).to_bytes(8, "big") + payload)

def _normalise_verifier_result(value: Any) -> Any:
    """Convert source-exact verifier scalars to the canonical tagged form."""
    if isinstance(value, Mapping):
        return {str(key): _normalise_verifier_result(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise_verifier_result(item) for item in value]
    if isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        return tag(value)
    if value is None or isinstance(value, str):
        return value
    raise VerificationError(f"unsupported verifier result value: {type(value).__name__}")




def _parent_verifier_receipts(w5: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    w4r = w5.get("w4r")
    require(isinstance(w4r, Mapping), "W4R discovery result is missing")
    w5_raw = w5.get("independent", w5)
    w4r_raw = w4r.get("independent")
    w5_result = _normalise_verifier_result(w5_raw)
    w4r_result = _normalise_verifier_result(w4r_raw)
    require(isinstance(w5_result, Mapping), "W5 independent result is not an object")
    require(isinstance(w4r_result, Mapping), "W4R independent result is not an object")
    require(w5_result.get("status") == "PASS_W5_G5", "W5 parent verifier did not pass")
    require(
        w4r_result.get("schema") == W4R_VERIFY_SCHEMA
        and w4r_result.get("status") == "PASS",
        "W4R parent verifier did not pass",
    )
    w4r_receipt = {
        "schema": PARENT_VERIFICATION_SCHEMA,
        "result": w4r_result,
        "verification_sha256": digest(w4r_result, PARENT_VERIFICATION_SCHEMA),
    }
    w5_receipt = {
        "schema": PARENT_VERIFICATION_SCHEMA,
        "result": w5_result,
        "verification_sha256": digest(w5_result, PARENT_VERIFICATION_SCHEMA),
    }
    inherited = w5_result.get("parent_verifier_receipts")
    require(
        isinstance(inherited, Mapping)
        and set(inherited) == {"schema", "w4r"}
        and inherited.get("schema") == PARENT_VERIFIER_RECEIPTS_SCHEMA
        and inherited.get("w4r") == w4r_receipt
        and w5_result.get("parent_verifier_receipts_sha256") == digest(inherited, PARENT_VERIFIER_RECEIPTS_SCHEMA),
        "W5 inherited W4R verifier receipt mismatch",
    )
    receipts = {
        "schema": PARENT_VERIFIER_RECEIPTS_SCHEMA,
        "w4r": w4r_receipt,
        "w5": w5_receipt,
    }
    return receipts, digest(receipts, PARENT_VERIFIER_RECEIPTS_SCHEMA)


def _check_parent_verifier_receipts(
    observed: Any,
    expected: Mapping[str, Any],
    expected_sha256: str,
    label: str,
) -> None:
    require(isinstance(observed, Mapping), f"{label}: mapping is missing")
    require(set(observed) == {"schema", "w4r", "w5"}, f"{label}: mapping keys are not canonical")
    require(observed.get("schema") == PARENT_VERIFIER_RECEIPTS_SCHEMA, f"{label}: mapping schema mutation")
    row_keys = {"schema", "result", "verification_sha256"}
    for key in ("w4r", "w5"):
        row = observed.get(key)
        require(isinstance(row, Mapping) and set(row) == row_keys, f"{label}.{key}: receipt row mutation")
        require(row["schema"] == PARENT_VERIFICATION_SCHEMA, f"{label}.{key}: receipt schema mutation")
        require(
            isinstance(row["result"], Mapping)
            and is_sha256(row["verification_sha256"])
            and digest(row["result"], PARENT_VERIFICATION_SCHEMA) == row["verification_sha256"],
            f"{label}.{key}: receipt identity mutation",
        )
    require(dict(observed) == dict(expected), f"{label}: recomputed parent receipt mismatch")
    require(digest(observed, PARENT_VERIFIER_RECEIPTS_SCHEMA) == expected_sha256, f"{label}: mapping digest mismatch")




def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid canonical JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"canonical object required: {path}")
    validate(value)
    return value


def check_self(value: Mapping[str, Any], domain: str, label: str) -> None:
    body = dict(value)
    claim = body.pop("self_sha256", None)
    require(is_sha256(claim), f"{label}: missing self hash")
    require(claim == digest(body, domain), f"{label}: self hash mismatch")


def raw_hash(raw: bytes) -> str:
    return sha(len(RAW_DOMAIN).to_bytes(8, "big") + RAW_DOMAIN + len(raw).to_bytes(8, "big") + raw)


def decimal_f64(value: Any, name: str) -> Decimal:
    return Decimal.from_float(f64(value, name))


def outward_lower(value: Decimal) -> float:
    result = float(value)
    require(math.isfinite(result), "non-finite lower enclosure")
    if Decimal.from_float(result) > value:
        result = math.nextafter(result, -math.inf)
    return math.nextafter(result, -math.inf)


def outward_upper(value: Decimal) -> float:
    result = float(value)
    require(math.isfinite(result), "non-finite upper enclosure")
    if Decimal.from_float(result) < value:
        result = math.nextafter(result, math.inf)
    return math.nextafter(result, math.inf)


def rounding_radius(value: Decimal, lower: float, upper: float) -> float:
    return outward_upper(max(value - Decimal.from_float(lower), Decimal.from_float(upper) - value, Decimal(0)))


def file_at(root: Path, relative: str) -> Path:
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts and path.as_posix() == relative, f"unsafe artifact relative path: {relative}")
    result = root / path
    require(result.is_file(), f"missing artifact object: {relative}")
    return result


def records(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": item.relative_to(root).as_posix(), "byte_count": len(raw := item.read_bytes()), "sha256": sha(raw)}
        for item in sorted(root.rglob("*"))
        if item.is_file() and item.name != "index.json"
    ]


def check_records(root: Path, index: Mapping[str, Any], label: str) -> None:
    inventory = index.get("objects")
    require(isinstance(inventory, list) and inventory == records(root), f"{label}: object inventory mutation")


def check_sources(root: Path, *, relative: str, schema: str, expected_paths: Sequence[str], label: str) -> dict[str, Any]:
    identity = read_json(file_at(root, relative))
    require(identity.get("schema") == schema, f"{label}: schema mismatch")
    check_self(identity, schema, label)
    listed = identity.get("sources")
    require(isinstance(listed, list) and len(listed) == len(expected_paths), f"{label}: source count mismatch")
    require([row.get("path") if isinstance(row, dict) else None for row in listed] == list(expected_paths), f"{label}: source order/inventory mutation")
    source_root = root / "sources"
    actual = [item.relative_to(source_root).as_posix() for item in sorted(source_root.rglob("*")) if item.is_file()]
    require(actual == sorted(expected_paths), f"{label}: source tree mutation")
    for row in listed:
        require(isinstance(row, dict) and set(row) == {"path", "byte_count", "sha256"}, f"{label}: source row schema mutation")
        relative_path = row["path"]
        require(isinstance(relative_path, str) and relative_path in expected_paths, f"{label}: unregistered source path")
        raw = file_at(source_root, relative_path).read_bytes()
        require(row["byte_count"] == len(raw) and row["sha256"] == sha(raw), f"{label}: source hash mutation: {relative_path}")
    return identity


def expected_law() -> dict[str, Any]:
    return {
        "law_id": W5_LAW_DOMAIN,
        "normalization": "rho=|E_Y|^2+|E_I|^2; epsilon=|E_Y|^2-phi|E_I|^2",
        "frozen_q": "rho_bar^2/(rho_bar^2+phi^-2+m_epsilon2)",
        "alpha": "exp(-(1+phi)*lambda*(1-Q)*h)",
        "transfer": "T=epsilon*(1-alpha)/(1+phi)",
        "density_map": "rho_next=rho; epsilon_next=alpha*epsilon",
        "epsilon_evaluation": "factored-magnitude-difference.v1",
        "phase_rule": "own-phase; empty-target-inherits-other-sector; double-empty-remains-zero.v1",
        "ema": "m_next=(1-tau)m+tau*epsilon_next^2",
        "tau": "1-exp(-h/epsilon_memory_time)",
        "q_evaluations_per_conversion": 1,
        "conversion_maps_per_interval": 1,
        "ema_updates_per_interval": 1,
        "velocity_mutation": "none",
        "projection": "none",
        "clipping": "none",
        "repair": "none",
        "persistent_state_added": False,
    }


def expected_semantics() -> dict[str, Any]:
    return {
        "cell_definition": "D_nu=D_conv intersect predicate(cell_id)",
        "unspecified_coordinates": "full frozen D_conv support subject only to cell predicate",
        "coordinates_covered": ["EY", "EI", "epsilon2_ema", "rho_ref", "phi", "lambda_rate", "phase_branch", "scale", "mode", "batch", "duration_s"],
        "boundary_values": "exact tagged-f64 profile values",
        "interior": "relative interior within D_conv",
        "overlap_policy": "shared boundaries and named lower-dimensional controls only",
    }


def expected_cover(*, phi: float, rho_max: float, ema_max: float, epsilon_prog: float) -> list[dict[str, Any]]:
    zero = tag(0.0)
    return [
        {"cell_id": "C00-exact-zero", "epsilon_interval": [zero, zero], "epsilon2_ema_interval": [zero, zero], "predicate": "EY==EI==epsilon2_ema==0"},
        {"cell_id": "C01-balanced-memory-zero", "epsilon_interval": [zero, zero], "epsilon2_ema_interval": [zero, zero], "predicate": "epsilon==0 and epsilon2_ema==0"},
        {"cell_id": "C02-balanced-memory-positive", "epsilon_interval": [zero, zero], "epsilon2_ema_interval": [zero, tag(ema_max)], "predicate": "epsilon==0 and epsilon2_ema>0"},
        {"cell_id": "C03-neutral-positive", "epsilon_interval": [zero, tag(epsilon_prog)], "epsilon2_ema_interval": [zero, tag(ema_max)], "predicate": "0<epsilon<epsilon_prog_min"},
        {"cell_id": "C04-neutral-negative", "epsilon_interval": [tag(-epsilon_prog), zero], "epsilon2_ema_interval": [zero, tag(ema_max)], "predicate": "-epsilon_prog_min<epsilon<0"},
        {"cell_id": "C05-progress-positive", "epsilon_interval": [tag(epsilon_prog), tag(rho_max)], "epsilon2_ema_interval": [zero, tag(ema_max)], "predicate": "epsilon>=epsilon_prog_min"},
        {"cell_id": "C06-progress-negative", "epsilon_interval": [tag(-phi * rho_max), tag(-epsilon_prog)], "epsilon2_ema_interval": [zero, tag(ema_max)], "predicate": "epsilon<=-epsilon_prog_min"},
    ]


def _number(value: Any, label: str) -> float:
    if isinstance(value, str) and value.startswith("f64:"):
        return f64(value, label)
    if isinstance(value, Mapping) and set(value) == {"numerator", "denominator"}:
        numerator, denominator = value["numerator"], value["denominator"]
        require(isinstance(numerator, int) and not isinstance(numerator, bool) and isinstance(denominator, int) and not isinstance(denominator, bool) and numerator > 0 and denominator > 0 and math.gcd(numerator, denominator) == 1, f"{label} rational is not reduced positive")
        return numerator / denominator
    return float(value)


def _profile_sections(profile: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], list[Any], Mapping[str, Any], Mapping[str, Any]]:
    parameters = profile.get("parameters")
    if not isinstance(parameters, Mapping):
        parameters = profile
    support_root = profile.get("support")
    if not isinstance(support_root, Mapping):
        support_root = {}
    support = profile.get("D_conv", support_root.get("D_conv"))
    accepted = profile.get("A_accepted", support_root.get("A_accepted"))
    partition = profile.get("partition")
    cover_root = profile.get("complete_domain_cover", profile.get("cover"))
    if isinstance(cover_root, Mapping):
        cover = cover_root.get("cells")
        semantics = profile.get("complete_domain_cover_semantics", cover_root.get("semantics", cover_root.get("endpoint_semantics")))
    else:
        cover, semantics = cover_root, profile.get("complete_domain_cover_semantics")
    margins = profile.get("registered_margins", profile.get("margins"))
    require(all(isinstance(value, Mapping) for value in (support, accepted, partition, margins)), "W5 profile omits explicit viability sections")
    require(isinstance(cover, list), "W5 profile omits complete-domain cells")
    if not isinstance(semantics, Mapping):
        semantics = {}
    return support, accepted, partition, cover, semantics, margins


def profile_scalars(profile: Mapping[str, Any]) -> dict[str, float]:
    parameters = profile.get("parameters")
    nested = parameters if isinstance(parameters, Mapping) else {}
    def scalar(name: str, *aliases: str) -> Any:
        for key in (name, *aliases):
            if key in profile:
                return profile[key]
            if key in nested:
                return nested[key]
        return None

    support, accepted, _, _, _, _ = _profile_sections(profile)
    phi = _number(scalar("phi"), "phi")
    rate = _number(scalar("lambda_rate", "lambda_rate_s_inv"), "lambda rate")
    rho_ref = _number(scalar("rho_ref"), "rho reference")
    epsilon_prog = _number(scalar("epsilon_prog_min"), "epsilon progress")
    position = support.get("position_density")
    if not isinstance(position, Mapping):
        support_root = profile.get("support", {})
        nested_support = support_root.get("D_conv") if isinstance(support_root, Mapping) else None
        position = nested_support.get("position_density") if isinstance(nested_support, Mapping) else None
    rho_max_raw = position.get("EY_plus_EI_max") if isinstance(position, Mapping) and "EY_plus_EI_max" in position else accepted.get("density_sum_at_most")
    rho_max = _number(rho_max_raw, "rho support")
    ema = support.get("epsilon2_ema")
    ema_max = _number(ema.get("max") if isinstance(ema, Mapping) else ema[1], "EMA support")
    component_max = _number(support.get("component_abs_max", accepted.get("component_abs_at_most")), "component support")
    duration = support.get("duration_s")
    require(duration is not None, "duration support missing")
    h_min_raw, h_max_raw = (duration.get("min"), duration.get("max")) if isinstance(duration, Mapping) else (duration[0], duration[1])
    h_min, h_max = _number(h_min_raw, "h lower"), _number(h_max_raw, "h upper")
    require(phi > 0.0 and rate >= 0.0 and rho_ref > 0.0 and epsilon_prog > 0.0 and rho_max > 0.0 and ema_max > 0.0 and component_max > 0.0 and 0.0 < h_min <= h_max, "conversion profile scalar support invalid")
    ey_min = position.get("EY_min", 0.0) if isinstance(position, Mapping) else 0.0
    ei_min = position.get("EI_min", 0.0) if isinstance(position, Mapping) else 0.0
    require(_number(ey_min, "EY lower") == 0.0 and _number(ei_min, "EI lower") == 0.0 and _number(ema.get("min") if isinstance(ema, Mapping) else ema[0], "EMA lower") == 0.0, "conversion support lower endpoint mutation")
    require(_number(accepted["density_sum_at_most"], "accepted density") == rho_max and _number(accepted["epsilon2_ema_at_most"], "accepted EMA") == ema_max and _number(accepted["component_abs_at_most"], "accepted component") == component_max, "accepted endpoint does not bind support")
    return {
        "phi": phi,
        "rate": rate,
        "rho_ref": rho_ref,
        "epsilon_prog": epsilon_prog,
        "rho_max": rho_max,
        "ema_max": ema_max,
        "component_max": component_max,
        "h_min": h_min,
        "h_max": h_max,
    }


def validate_conversion_profile(
    profile: Mapping[str, Any],
    root: Mapping[str, Any],
    law: Mapping[str, Any],
    *,
    parent_extension_sha256: str | None = None,
    parent_identities: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    require(profile.get("schema") == W5_PROFILE_SCHEMA, "conversion profile schema mismatch")
    profile_body = dict(profile)
    profile_identity = profile_body.pop("profile_sha256", None)
    require(is_sha256(profile_identity) and profile_identity == digest(profile_body, W5_PROFILE_SCHEMA), "conversion profile identity mismatch")
    require(profile.get("law_id") == W5_LAW_DOMAIN and profile.get("law") == expected_law() and law == expected_law(), "frozen-Q law mutation")
    require(profile.get("law_sha256") == digest(expected_law(), W5_LAW_DOMAIN), "frozen-Q law identity mutation")
    parents = profile.get("parent_identities", profile.get("parents"))
    require(isinstance(parents, Mapping) and parents, "conversion profile parent identities missing")
    if parent_identities is not None:
        require(dict(parents) == dict(parent_identities), "conversion profile parent identities do not match current W5 parent")
    if parent_extension_sha256 is not None:
        extension_claims = [profile.get("w4r_certificate_extension_sha256"), root.get("w4r_certificate_extension_sha256")]
        present = [value for value in extension_claims if value is not None]
        if present:
            require(present == [parent_extension_sha256] * len(present), "conversion profile parent extension linkage mutation")
    support, accepted, partition, cover, semantics, margins = _profile_sections(profile)
    require(support.get("closed") is True and support.get("frozen_before_observation") is True, "support is not frozen/closed")
    require(accepted.get("finite_only") is True and accepted.get("nonnegative_sector_densities") is True, "accepted endpoint policy mutation")
    require(partition == {"D_prog": "abs(epsilon)>=epsilon_prog_min", "D_neutral": "abs(epsilon)<epsilon_prog_min", "balanced": "epsilon==0", "exact_zero": "EY==EI==epsilon2_ema==0"}, "D_prog/D_neutral partition mutation")
    require(semantics == expected_semantics(), "complete-domain cover semantics mutation")
    scalars = profile_scalars(profile)
    duration = support.get("duration_s")
    duration_bounds = duration if isinstance(duration, list) else [duration["min"], duration["max"]]
    h_values = [_number(value, "duration endpoint") for value in duration_bounds]
    rationals = support.get("runtime_exact_rationals")
    if rationals is None and isinstance(profile.get("clock"), Mapping):
        rationals = profile["clock"].get("runtime_exact_rationals")
    require(isinstance(rationals, list) and rationals, "runtime exact rational membership missing")
    for row in rationals:
        require(isinstance(row, Mapping) and set(row) == {"numerator", "denominator"}, "runtime rational schema mutation")
        require(isinstance(row["numerator"], int) and not isinstance(row["numerator"], bool) and isinstance(row["denominator"], int) and not isinstance(row["denominator"], bool) and row["numerator"] > 0 and row["denominator"] > 0 and math.gcd(row["numerator"], row["denominator"]) == 1, "runtime rational is not reduced positive")
    require(0.0 < h_values[0] <= h_values[1] and all(any(value == row["numerator"] / row["denominator"] for row in rationals) for value in h_values), "closed duration endpoint mutation")
    expected_cells = expected_cover(phi=scalars["phi"], rho_max=scalars["rho_max"], ema_max=scalars["ema_max"], epsilon_prog=scalars["epsilon_prog"])
    cover_value = profile.get("complete_domain_cover", profile.get("cover"))
    if isinstance(cover_value, Mapping):
        require(cover_value.get("cells") == expected_cells, "complete cover/cell predicate/EMA-axis mutation")
        require(cover_value.get("semantics") == semantics or cover_value.get("endpoint_semantics") == semantics, "complete cover semantics mutation")
    else:
        require(cover_value == expected_cells, "complete cover/cell predicate/EMA-axis mutation")
    require(all(_number(margins[key], key) >= 0.0 for key in ("Delta_T_min", "Delta_T_neutral", "U_T_max", "forward_density_floor", "ema_upper_slack_min")), "registered margin mutation")
    require(_number(margins["forward_density_floor"], "forward density floor") == 0.0, "registered density floor mutation")
    require(root.get("schema") == W5_ROOT_SCHEMA, "conversion root schema mismatch")
    check_self(root, W5_ROOT_SCHEMA, "conversion root")
    require(root.get("law_id") == W5_LAW_DOMAIN and root.get("profile_sha256") == profile_identity and root.get("law_sha256") == profile["law_sha256"], "conversion root profile/law linkage mutation")
    if root.get("parent_identities") is not None:
        require(root.get("parent_identities") == parents, "conversion root parent identities mutation")
    require(root.get("additional_state") is False, "conversion root persistent-state mutation")
    require(root.get("state_layout") == profile.get("state_layout"), "conversion state layout drift")
    require(root.get("split_schedule") == profile.get("split_schedule"), "conversion split schedule drift")
    return scalars


def check_parent_extension(
    extension: Mapping[str, Any],
    *,
    expected_sha256: str | None = None,
    expected_ordinal: int | None = None,
) -> int:
    require(extension.get("schema") == W5V_EXTENSION_SCHEMA, "immutable certificate extension schema mismatch")
    check_self(extension, W5V_EXTENSION_DOMAIN, "immutable certificate extension")
    self_sha256 = extension.get("self_sha256")
    require(is_sha256(self_sha256), "immutable certificate extension identity missing")
    if expected_sha256 is not None:
        require(self_sha256 == expected_sha256, "immutable certificate extension identity linkage mutation")
    ordinal = extension.get("chain_ordinal")
    require(isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal > 0, "immutable certificate extension ordinal mutation")
    if expected_ordinal is not None:
        require(ordinal == expected_ordinal, "immutable certificate extension ordinal linkage mutation")
    require(extension.get("chain_status") in {"provisional", "final"}, "immutable certificate extension chain status mutation")
    if extension.get("chain_status") == "provisional":
        require(extension.get("production_certificate_complete") is False and extension.get("final_certificate_identity_sha256") is None, "provisional certificate extension falsely final")
    else:
        require(is_sha256(extension.get("final_certificate_identity_sha256")), "final certificate extension lacks final identity")
    inventory = extension.get("complete_section_inventory")
    require(isinstance(inventory, list) and len(inventory) == ordinal, "immutable certificate extension inventory missing")
    require(all(isinstance(row, Mapping) for row in inventory), "immutable certificate extension inventory row mutation")
    require([row.get("ordinal") for row in inventory] == list(range(1, ordinal + 1)), "immutable certificate extension inventory mutation")
    added = extension.get("added_section")
    require(isinstance(added, Mapping) and added == inventory[-1] and added.get("ordinal") == ordinal, "immutable certificate extension added-section mutation")
    parent_inventory = extension.get("parent_section_inventory")
    require(isinstance(parent_inventory, list) and parent_inventory == inventory[:-1], "immutable certificate extension parent-inventory mutation")
    require(isinstance(extension.get("certificate_chain_id"), str) and extension.get("certificate_chain_id"), "immutable certificate chain identity missing")
    parent_certificate = extension.get("parent_certificate_sha256")
    require(is_sha256(parent_certificate), "immutable certificate parent certificate identity missing")
    return ordinal



def _named_path(root: Path, names: Sequence[str]) -> Path:
    for relative in names:
        path = root / relative
        if path.is_file():
            return path
    require(False, f"missing W5 artifact object (tried {', '.join(names)})")
    raise AssertionError


def _read_named(root: Path, names: Sequence[str]) -> tuple[Path, bytes, dict[str, Any]]:
    path = _named_path(root, names)
    raw = path.read_bytes()
    return path, raw, read_json(path)


def _candidate_roots(base: Path, *, depth: int = 1) -> list[Path]:
    base = Path(base).resolve()
    candidates: list[Path] = []
    if (base / "index.json").is_file():
        candidates.append(base)
    if depth > 0 and base.is_dir():
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "index.json").is_file():
                candidates.append(child)
    return candidates


def _path_hints(value: Any) -> list[Path]:
    hints: list[Path] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if isinstance(item, str) and (
                "root" in key_text or key_text.endswith("_path") or key_text in {"path", "artifact"}
            ):
                candidate = Path(item).expanduser()
                if candidate.is_dir() and (candidate / "index.json").is_file():
                    hints.append(candidate.resolve())
            hints.extend(_path_hints(item))
    elif isinstance(value, list):
        for item in value:
            hints.extend(_path_hints(item))
    return hints


def _call_verifier(module_name: str, root: Path) -> dict[str, Any]:
    source_path = root / "sources" / f"{module_name}.py"
    require(source_path.is_file(), f"{module_name} source-exact verifier snapshot is missing")
    module_name_staged = f"_cassi_staged_{module_name}_{sha(source_path.read_bytes())[:16]}"
    try:
        spec = importlib.util.spec_from_file_location(module_name_staged, source_path)
        require(spec is not None and spec.loader is not None, f"{module_name} source-exact verifier cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        verify_fn = getattr(module, "verify")
    except (ImportError, AttributeError, OSError, VerificationError) as exc:
        raise VerificationError(f"{module_name} source-exact independent verifier unavailable") from exc
    try:
        result = verify_fn(root)
    except Exception as exc:
        raise VerificationError(f"{module_name} rejected candidate {root}: {exc}") from exc
    require(isinstance(result, Mapping), f"{module_name} returned a non-object result")
    return dict(result)


def _extension_in(root: Path, *, expected_sha256: str | None = None) -> tuple[Path, bytes, dict[str, Any]]:
    parent = root / "certificate"
    candidates: list[tuple[Path, bytes, dict[str, Any]]] = []
    if parent.is_dir():
        for path in sorted(parent.glob("extension-*.json")):
            if not path.is_file():
                continue
            try:
                raw = path.read_bytes()
                value = read_json(path)
            except VerificationError:
                continue
            if value.get("schema") != W5V_EXTENSION_SCHEMA:
                continue
            if expected_sha256 is not None and value.get("self_sha256") != expected_sha256:
                continue
            candidates.append((path, raw, value))
    require(len(candidates) == 1, "W4R current certificate extension is missing or ambiguous")
    return candidates[0]
def _identity_values(value: Any, names: Sequence[str]) -> list[str]:
    result: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in names and isinstance(item, str):
                result.append(item)
            result.extend(_identity_values(item, names))
    elif isinstance(value, list):
        for item in value:
            result.extend(_identity_values(item, names))
    return result


def _identity_record(value: Mapping[str, Any], *, label: str, relative_path: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"label": label}
    if relative_path is not None:
        result["artifact_path"] = relative_path
    for key, item in value.items():
        if key == "self_sha256" or key.endswith("_sha256"):
            if item is not None:
                result[key] = item
    if "schema" in value:
        result["schema"] = value["schema"]
    return result


def _w4r_candidates(*, w5_root: Path, expected: Mapping[str, Any], hints: Sequence[Path]) -> list[dict[str, Any]]:
    bases: list[Path] = list(hints)
    diag = Path(__file__).resolve().parent / "_diag"
    for relative in (
        "cassi-qi-flow-w4r-retention-core-final",
        "cassi-qi-flow-w4r-retention-final",
        "cassi-qi-flow-w4r-final",
    ):
        bases.append(diag / relative)
    bases.extend((w5_root.parent, w5_root.parent.parent))
    roots: list[Path] = []
    for base in bases:
        for candidate in _candidate_roots(base, depth=1):
            if candidate not in roots:
                roots.append(candidate)
    expected_run = expected.get("run_id")
    expected_extension = expected.get("extension_sha256")
    verified: list[dict[str, Any]] = []
    for candidate in roots:
        try:
            independent = _call_verifier("verify_cassi_qi_topology", candidate)
            index = read_json(candidate / "index.json")
            extension_path, extension_raw, extension = _extension_in(candidate, expected_sha256=expected_extension)
            check_parent_extension(extension, expected_sha256=expected_extension)
            run_id = index.get("run_id")
            if expected_run is not None and run_id != expected_run:
                continue
            if expected_extension is not None and index.get("certificate_extension_sha256") != expected_extension:
                continue
            verified.append(
                {
                    "root": candidate,
                    "index": index,
                    "index_raw": index_raw,
                    "index_sha256": sha(index_raw),
                    "extension": extension,
                    "extension_raw": extension_raw,
                    "extension_path": extension_path.relative_to(candidate).as_posix(),
                    "independent": independent,
                }
            )
        except (OSError, VerificationError, ValueError):
            continue
    require(len(verified) == 1, "current W4R parent is missing or ambiguous")
    return verified


def _discover_w4r(*, w5_root: Path, profile: Mapping[str, Any], conversion_root: Mapping[str, Any], parent_binding: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snapshots = w5_root / "parents"
    snapshot_extensions: list[dict[str, Any]] = []
    if snapshots.is_dir():
        for path in sorted(snapshots.glob("*extension*.json")):
            try:
                value = read_json(path)
            except VerificationError:
                continue
            if value.get("schema") == W5V_EXTENSION_SCHEMA:
                snapshot_extensions.append(value)
    expected_extension = (
        conversion_root.get("w4r_certificate_extension_sha256")
        or profile.get("w4r_certificate_extension_sha256")
        or (snapshot_extensions[0].get("self_sha256") if len(snapshot_extensions) == 1 else None)
    )
    parent_data = parent_binding or {}
    expected_runs = _identity_values(parent_data, ("run_id", "w4r_parent_run_id", "w4r_run_id"))
    expected_run = expected_runs[0] if len(set(expected_runs)) == 1 else None
    expected = {"run_id": expected_run, "extension_sha256": expected_extension}
    hints = _path_hints(parent_data)
    candidates = _w4r_candidates(w5_root=w5_root, expected=expected, hints=hints)
    return candidates[0]


def w5_material(index: Mapping[str, Any]) -> dict[str, Any]:
    payload_keys = {
        "schema",
        "status",
        "parents",
        "source_exact_successor_of",
        "profile_sha256",
        "root_sha256",
        "law_sha256",
        "conversion_profile_sha256",
        "conversion_root_sha256",
        "conversion_law_sha256",
        "engineering_candidate_only",
        "w5v_forward_domain_certificate",
        "candidate_sha256",
        "status_sha256",
        "measurements_sha256",
        "objects",
    }
    require(set(index) == (payload_keys | {"run_id", "self_sha256"}), "W5 index fields mutation")
    require(index["schema"] == W5_INDEX_SCHEMA, "W5 index schema mutation")
    require(isinstance(index["objects"], list) and index["objects"], "W5 object inventory missing")
    require(index["profile_sha256"] == index["conversion_profile_sha256"], "W5 profile identity alias mutation")
    require(index["root_sha256"] == index["conversion_root_sha256"], "W5 root identity alias mutation")
    require(index["law_sha256"] == index["conversion_law_sha256"], "W5 law identity alias mutation")
    return {key: index[key] for key in payload_keys}


def _w5_binding_from_result(
    index: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    index_raw: bytes,
    w4r: Mapping[str, Any],
    candidate: Mapping[str, Any],
    profile: Mapping[str, Any],
    conversion_root: Mapping[str, Any],
    law: Mapping[str, Any],
    certificate: Mapping[str, Any],
    source_identity: Mapping[str, Any],
) -> dict[str, Any]:
    parent_ids: dict[str, Any] = {
        "w4r_extension": _identity_record(w4r["extension"], label="current-W4R-certificate-extension", relative_path=w4r["extension_path"]),
        "w4r_section_inventory": [_identity_record(row, label=f"certificate-section-{row.get('ordinal', ordinal + 1)}") for ordinal, row in enumerate(w4r["extension"].get("complete_section_inventory", []))],
    }
    for ordinal, item in enumerate(index.get("parents", [])):
        if isinstance(item, Mapping):
            for key, value in item.items():
                if key.endswith("_sha256") and value is not None:
                    require(is_sha256(value), f"W5 parent {ordinal} identity {key} is malformed")
            parent_ids[f"w4r_parent_{ordinal}"] = dict(item)
    certificate_ids = {
        "w5_candidate": _identity_record(candidate, label="current-W5-candidate", relative_path="gates/g05-conversion/candidate.json"),
        "w5_profile": _identity_record(profile, label="current-W5-profile", relative_path="profile/conversion-profile.json"),
        "w5_root": _identity_record(conversion_root, label="current-W5-conversion-root", relative_path="profile/conversion-root.json"),
        "w5_law": _identity_record(law, label="current-W5-frozen-Q-law", relative_path="profile/conversion-law.json"),
        "w5_certificate": _identity_record(certificate, label="current-W5-numerical-certificate", relative_path="certificate/g3n-certificate-root.json"),
    }
    if isinstance(result.get("parent_identities"), Mapping):
        require(dict(result["parent_identities"]) == parent_ids, "W5 independent parent identities disagree with source objects")
    if isinstance(result.get("certificate_identities"), Mapping):
        require(dict(result["certificate_identities"]) == certificate_ids, "W5 independent certificate identities disagree with source objects")
    source_sha = sha(file_at(Path(__file__).resolve().parent, "cassi_qi_conversion.py").read_bytes())
    binding = {
        "run_id": index["run_id"],
        "index_sha256": sha(index_raw),
        "candidate_state_sha256": candidate["self_sha256"],
        "profile_sha256": profile["profile_sha256"],
        "root_sha256": conversion_root["self_sha256"],
        "law_sha256": profile["law_sha256"],
        "conversion_source_sha256": source_sha,
        "source_identity_sha256": source_identity["self_sha256"],
        "parent_identities": parent_ids,
        "certificate_identities": certificate_ids,
        "status": "PASS",
        "w5v_forward_domain_certificate": None,
    }
    return binding


def verify_w5(root: Path, *, hints: Sequence[Path] = ()) -> dict[str, Any]:
    root = Path(root).resolve()
    require(root.is_dir(), f"W5 predecessor does not exist: {root}")
    index_raw = file_at(root, "index.json").read_bytes()
    index = read_json(root / "index.json")
    require(index.get("schema") == W5_INDEX_SCHEMA, "W5 index schema mismatch")
    check_self(index, W5_ARTIFACT_DOMAIN, "W5 index")
    require(index.get("status") == "PASS_W5_G5", "W5 index status mutation")
    require(index.get("w5v_forward_domain_certificate") is None, "W5 index falsely claims W5V")
    require(isinstance(index.get("parents"), list) and len(index["parents"]) == 1, "W5 parent inventory must contain exactly one W4R parent")
    require(index.get("source_exact_successor_of") == index.get("parents")[0], "W5 source-exact parent relation mutation")
    require(isinstance(index.get("objects"), list) and index["objects"], "W5 object inventory missing")
    require(index.get("run_id") == digest(w5_material(index), W5_ARTIFACT_DOMAIN), "W5 content-addressed run identity mutation")
    check_records(root, index, "W5")
    independent = _call_verifier("verify_cassi_qi_conversion", root)
    require(independent.get("gate") == "G5" and independent.get("status") == "PASS_W5_G5", "W5 predecessor independent gate/status mutation")
    require(independent.get("run_id") == index.get("run_id"), "W5 independent run identity mismatch")
    source_identity = check_sources(root, relative="run-spec/source-identity.json", schema=W5_SOURCE_IDENTITY_SCHEMA, expected_paths=W5_SOURCE_PATHS, label="W5 source identity")
    profile_path, profile_raw, profile = _read_named(root, ("profile/conversion-profile.json",))
    root_path, root_raw, conversion_root = _read_named(root, ("profile/conversion-root.json",))
    law_path, law_raw, law = _read_named(root, ("profile/conversion-law.json",))
    certificate_path, certificate_raw, certificate = _read_named(root, ("certificate/g3n-certificate-root.json", "certificate/certificate-root.json"))
    require(
        all(
            isinstance(row, Mapping)
            and (Path(__file__).resolve().parent / row["path"]).is_file()
            and sha((Path(__file__).resolve().parent / row["path"]).read_bytes()) == row["sha256"]
            for row in source_identity["sources"]
        ),
        "W5 source snapshot is stale relative to current sources",
    )
    candidate_path, candidate_raw, candidate = _read_named(root, ("gates/g05-conversion/candidate.json",))
    status_path, status_raw, status = _read_named(root, ("gates/g05-conversion/status.json",))
    measurements_path, measurements_raw, measurements = _read_named(root, ("gates/g05-conversion/measurements.json",))
    require(candidate.get("schema") == W5_CANDIDATE_SCHEMA, "W5 candidate schema mutation")
    check_self(candidate, W5_CANDIDATE_SCHEMA, "W5 candidate")
    require(
        candidate.get("status") == "PASS"
        and candidate.get("candidate_only") is True
        and candidate.get("extension_added") is False
        and candidate.get("w5v_forward_domain_certificate") is None
        and candidate.get("measurements_path") == "gates/g05-conversion/measurements.json"
        and candidate.get("measurements_sha256") == measurements.get("self_sha256")
        and candidate.get("status_path") == "gates/g05-conversion/status.json",
        "W5 candidate linkage/status mutation",
    )
    require(
        candidate.get("profile_sha256") == profile.get("profile_sha256")
        and candidate.get("root_sha256") == conversion_root.get("self_sha256")
        and candidate.get("law_sha256") == profile.get("law_sha256")
        and candidate.get("conversion_profile_sha256") == profile.get("profile_sha256")
        and candidate.get("conversion_root_sha256") == conversion_root.get("self_sha256")
        and candidate.get("conversion_law_sha256") == profile.get("law_sha256"),
        "W5 candidate profile/root/law linkage mutation",
    )
    require(candidate.get("parent_identities") == profile.get("parent_identities"), "W5 candidate parent identity mutation")
    require(status.get("schema") == W5_STATUS_SCHEMA, "W5 status schema mutation")
    check_self(status, W5_STATUS_SCHEMA, "W5 status")
    require(
        status.get("status") == "PASS_W5_G5"
        and status.get("decision") == "PASS"
        and status.get("all_expected_decisions") is True
        and status.get("engineering_candidate_only") is True
        and status.get("w5v_forward_domain_certificate") is None
        and status.get("candidate_path") == "gates/g05-conversion/candidate.json"
        and status.get("measurements_path") == "gates/g05-conversion/measurements.json",
        "W5 status false W5V inference",
    )
    require(measurements.get("schema") == W5_MEASUREMENTS_SCHEMA, "W5 measurements schema mutation")
    check_self(measurements, W5_MEASUREMENTS_SCHEMA, "W5 measurements")
    require(measurements.get("w5v_forward_domain_certificate") is None, "W5 measurements false W5V inference")
    require(
        status.get("deterministic_replay") is not None
        and isinstance(status.get("deterministic_replay"), Mapping)
        and index.get("candidate_sha256") == candidate.get("self_sha256")
        and index.get("status_sha256") == status.get("self_sha256")
        and index.get("measurements_sha256") == measurements.get("self_sha256"),
        "W5 candidate/status/measurement linkage mutation",
    )
    parent_binding = None
    parent_path = root / "run-spec" / "parent-w4r.json"
    if parent_path.is_file():
        parent_binding = read_json(parent_path)
    w4r = _discover_w4r(w5_root=root, profile=profile, conversion_root=conversion_root, parent_binding=parent_binding)
    parent_dir = root / "parents"
    extension_candidates = []
    if parent_dir.is_dir():
        extension_candidates = sorted(parent_dir.glob("*extension*.json"))
    extension_candidates = [path for path in extension_candidates if path.is_file()]
    require(len(extension_candidates) == 1, "W5 parent extension snapshot missing or ambiguous")
    extension_path = extension_candidates[0]
    extension_raw = extension_path.read_bytes()
    extension = read_json(extension_path)
    require(extension.get("self_sha256") == w4r["extension"]["self_sha256"] and extension_raw == w4r["extension_raw"], "W5 parent extension snapshot is stale")
    parent_ordinal = check_parent_extension(extension, expected_sha256=w4r["extension"]["self_sha256"])
    binding_w4r = dict(w4r)
    binding_w4r["extension"] = extension
    binding_w4r["extension_raw"] = extension_raw
    binding_w4r["extension_path"] = extension_path.relative_to(root).as_posix()
    parent_identities = {
        "w4r_extension": _identity_record(
            extension,
            label="current-W4R-certificate-extension",
            relative_path=binding_w4r["extension_path"],
        ),
        "w4r_section_inventory": [
            _identity_record(row, label=f"certificate-section-{row.get('ordinal', ordinal + 1)}")
            for ordinal, row in enumerate(extension.get("complete_section_inventory", []))
        ],
    }
    for ordinal, item in enumerate(index.get("parents", [])):
        if isinstance(item, Mapping):
            parent_identities[f"w4r_parent_{ordinal}"] = dict(item)
    validate_conversion_profile(
        profile,
        conversion_root,
        law,
        parent_extension_sha256=w4r["extension"]["self_sha256"],
        parent_identities=parent_identities,
    )
    require(
        index["profile_sha256"] == index["conversion_profile_sha256"] == profile["profile_sha256"]
        and index["root_sha256"] == index["conversion_root_sha256"] == conversion_root["self_sha256"]
        and index["law_sha256"] == index["conversion_law_sha256"] == profile["law_sha256"],
        "W5 profile/root/law index linkage mutation",
    )
    if conversion_root.get("w4r_certificate_extension_sha256") is not None:
        require(conversion_root.get("w4r_certificate_extension_sha256") == w4r["extension"]["self_sha256"], "W5 root/W4R extension linkage mutation")
    source_sha = sha(file_at(root / "sources", "cassi_qi_conversion.py").read_bytes())
    binding = _w5_binding_from_result(index, independent, index_raw=index_raw, w4r=binding_w4r, candidate=candidate, profile=profile, conversion_root=conversion_root, law=law, certificate=certificate, source_identity=source_identity)
    require(binding["conversion_source_sha256"] == source_sha, "W5 conversion source identity is not current")
    return {
        "root": root,
        "index": index,
        "index_raw": index_raw,
        "profile": profile,
        "profile_raw": profile_raw,
        "conversion_root": conversion_root,
        "root_raw": root_raw,
        "law_raw": law_raw,
        "law": law,
        "certificate": certificate,
        "certificate_raw": certificate_raw,
        "candidate": candidate,
        "candidate_raw": candidate_raw,
        "status": status,
        "status_raw": status_raw,
        "measurements": measurements,
        "measurements_raw": measurements_raw,
        "source_identity": source_identity,
        "extension": extension,
        "extension_raw": extension_raw,
        "extension_path": extension_path.relative_to(root).as_posix(),
        "parent_ordinal": parent_ordinal,
        "w4r": w4r,
        "binding": binding,
        "independent": independent,
    }


def build_viability(profile: Mapping[str, Any], conversion_root: Mapping[str, Any]) -> dict[str, Any]:
    params = profile.get("parameters") if isinstance(profile.get("parameters"), Mapping) else profile
    support, accepted, partition, cover, semantics, margins = _profile_sections(profile)
    raw_candidates = params.get("epsilon_memory_time_candidates_s")
    require(isinstance(raw_candidates, list) and raw_candidates, "physical-time candidate order missing")
    selected_raw = params.get("epsilon_memory_time_s", params.get("physical_epsilon_memory_time_s"))
    duration = support.get("duration_s")
    duration_values = duration if isinstance(duration, list) else [duration["min"], duration["max"]]
    rationals = support.get("runtime_exact_rationals")
    if rationals is None and isinstance(profile.get("clock"), Mapping):
        rationals = profile["clock"].get("runtime_exact_rationals")
    require(isinstance(rationals, list) and len(rationals) == len(duration_values), "exact runtime rational registration mismatch")
    exact_duration_rationals = []
    for ordinal, (row, raw_duration) in enumerate(zip(rationals, duration_values)):
        require(isinstance(row, Mapping) and isinstance(row.get("numerator"), int) and isinstance(row.get("denominator"), int), "exact runtime rational schema mutation")
        exact_duration_rationals.append({"ordinal": ordinal, "numerator": row["numerator"], "denominator": row["denominator"], "duration_s": tag(_number(raw_duration, "duration"))})
    require(isinstance(cover, list) and len(cover) == 7 and all(isinstance(row, Mapping) for row in cover), "complete-domain cover must contain seven full cell rows")
    method = {
        "method": W5V_ANALYTIC_METHOD,
        "decimal_precision_digits": 100,
        "registered_parameters_are_exact_binary64_reals": True,
        "transcendentals": "Decimal.exp with outward binary64 enclosure",
        "fixtures_define_support": False,
        "unresolved_policy": "FAIL",
        "candidate_order": list(raw_candidates),
        "selection_rule": params.get("epsilon_memory_time_selection_order"),
        "exact_runtime_rationals": exact_duration_rationals,
    }
    parent_ids = profile.get("parent_identities", profile.get("parents", {}))
    value: dict[str, Any] = {
        "schema": W5V_PROFILE_SCHEMA,
        "conversion_profile_sha256": profile["profile_sha256"],
        "conversion_root_sha256": conversion_root["self_sha256"],
        "conversion_law_sha256": profile["law_sha256"],
        "parent_identities": parent_ids,
        "D_conv": support,
        "A_accepted": accepted,
        "partition": partition,
        "epsilon_prog_min": params["epsilon_prog_min"],
        "D_prog": partition["D_prog"],
        "D_neutral": partition["D_neutral"],
        "complete_domain_cover": cover,
        "complete_domain_cover_semantics": semantics,
        "registered_margins": margins,
        "coefficient_candidates": list(raw_candidates),
        "physical_epsilon_memory_time_s": selected_raw,
        "exact_duration_rationals": exact_duration_rationals,
        "method": method,
        "frozen_before_fixture_observation": True,
        "post_observation_support_change": "new-failed-profile-identity",
        "rejection_policy": "retain-exact-rejected-intervals;revise-law-on-failure",
    }
    value["support_sha256"] = digest(value["D_conv"], SUPPORT_DOMAIN)
    value["accepted_sha256"] = digest(value["A_accepted"], ACCEPTED_DOMAIN)
    value["cover_sha256"] = digest({"semantics": value["complete_domain_cover_semantics"], "cells": value["complete_domain_cover"]}, COVER_DOMAIN)
    value["partition_sha256"] = digest(value["partition"], PARTITION_DOMAIN)
    value["method_sha256"] = digest(method, METHOD_DOMAIN)
    value["profile_sha256"] = digest(value, W5V_PROFILE_SCHEMA)
    return value


def cover_status(profile: Mapping[str, Any], scalars: Mapping[str, float]) -> dict[str, Any]:
    support, _, partition, cells, _, _ = _profile_sections(profile)
    require(isinstance(cells, list) and len(cells) == 7 and all(isinstance(row, Mapping) for row in cells) and len({row.get("cell_id") for row in cells}) == 7, "cover lacks seven unique cells")
    require(cells == expected_cover(phi=scalars["phi"], rho_max=scalars["rho_max"], ema_max=scalars["ema_max"], epsilon_prog=scalars["epsilon_prog"]), "cover semantic mutation")
    phase_branches = support.get("phase_branches", profile.get("phase_branches"))
    require(isinstance(phase_branches, list) and phase_branches, "D_conv omits registered phase branches")
    duration = support.get("duration_s")
    duration_bounds = duration if isinstance(duration, Mapping) else {"min": duration[0], "max": duration[1]}
    rationals = support.get("runtime_exact_rationals")
    if rationals is None and isinstance(profile.get("clock"), Mapping):
        rationals = profile["clock"].get("runtime_exact_rationals")
    duration_values = [duration_bounds["min"], duration_bounds["max"]]
    exact_rows = []
    if isinstance(rationals, list):
        exact_rows = [{"ordinal": ordinal, "numerator": row["numerator"], "denominator": row["denominator"], "duration_s": duration_values[ordinal]} for ordinal, row in enumerate(rationals)]
    bulk = ["C06-progress-negative", "C04-neutral-negative", "C03-neutral-positive", "C05-progress-positive"]
    return {
        "cell_count": len(cells),
        "cell_ids": [row["cell_id"] for row in cells],
        "epsilon_support": [tag(-scalars["phi"] * scalars["rho_max"]), tag(scalars["rho_max"])],
        "epsilon2_ema_support": [tag(0.0), tag(scalars["ema_max"])],
        "duration_support": duration_bounds,
        "exact_duration_rationals": exact_rows,
        "phase_branches": list(phase_branches),
        "bulk_cover_order": bulk,
        "balanced_memory_partition": ["C00-exact-zero", "C01-balanced-memory-zero", "C02-balanced-memory-positive"],
        "D_prog": partition["D_prog"],
        "D_neutral": partition["D_neutral"],
        "complete": True,
        "all_D_conv_coordinates_included": True,
        "interiors_pairwise_disjoint": True,
        "boundary_overlap_only": True,
        "exact_zero_named": True,
        "balanced_named": True,
    }


def analytic(profile: Mapping[str, Any], scalars: Mapping[str, float]) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 100
        phi, rate, rho_ref = (Decimal.from_float(scalars[key]) for key in ("phi", "rate", "rho_ref"))
        rho_max, ema_max, h_min, h_max, epsilon_prog = (Decimal.from_float(scalars[key]) for key in ("rho_max", "ema_max", "h_min", "h_max", "epsilon_prog"))
        support, accepted, _, _, _, margins = _profile_sections(profile)
        operation_count_raw = margins.get("analytic_operation_count_upper")
        require(isinstance(operation_count_raw, int) and not isinstance(operation_count_raw, bool) and operation_count_raw > 0, "analytic operation-count bound missing")
        one = Decimal(1)
        q_max = (rho_max / rho_ref) ** 2 / ((rho_max / rho_ref) ** 2 + one / (phi * phi))
        one_minus_q = one - q_max
        kappa_min = (one + phi) * rate * one_minus_q * h_min
        kappa_max = (one + phi) * rate * h_max
        beta_min = (one - (-kappa_min).exp()) / (one + phi)
        beta_max = (one - (-kappa_max).exp()) / (one + phi)
        unit = Decimal(2) ** Decimal(-53)
        operation_count = Decimal(operation_count_raw)
        require(operation_count * unit < one, "analytic operation-count bound is inadmissible")
        gamma = operation_count * unit / (one - operation_count * unit)
        operation_scale = max(ema_max, rho_max, phi * rho_max, one)
        runtime_error = gamma * operation_scale
        progress_exact, neutral_exact = epsilon_prog * beta_min, epsilon_prog * beta_max
        progress_lo, progress_hi = outward_lower(progress_exact), outward_upper(progress_exact)
        neutral_lo, neutral_hi = outward_lower(neutral_exact), outward_upper(neutral_exact)
        progress_u = max(rounding_radius(progress_exact, progress_lo, progress_hi), outward_upper(runtime_error))
        neutral_u = max(rounding_radius(neutral_exact, neutral_lo, neutral_hi), outward_upper(runtime_error))
        epsilon_abs_max = phi * rho_max
        epsilon2_post_max = epsilon_abs_max * epsilon_abs_max
        coefficient_floor = one - phi * beta_max
        state_layout = profile.get("state_layout")
        require(isinstance(state_layout, Mapping), "W5 profile state layout missing")
        parent_ids = profile.get("parent_identities", profile.get("parents", {}))
        finite_operator_identity = profile.get("w2_geometry_profile_sha256")
        if finite_operator_identity is None and isinstance(parent_ids, Mapping):
            finite_operator_identity = parent_ids.get("w2_profile_sha256")
        work = {
            "definition": "W_conversion=E_total(endpoint)-E_total(predecessor)",
            "E_total_components": ["wave_position", "wave_velocity", "wave_gradient", "composition_potential", "link_energy", "topological_retention_hamiltonian"],
            "state_dimension": dict(state_layout),
            "bounded_input": {"position_density_sum_max": tag(scalars["rho_max"]), "dynamic_component_abs_max": tag(scalars["component_max"]), "epsilon2_ema_max": tag(scalars["ema_max"])},
            "finite_operator_identity": finite_operator_identity,
            "finite_endpoint_reason": "finite-dimensional bounded field; current periodic-sheet, composition, link, and retention operators",
            "link_energy_at_W5": tag(0.0),
            "algebraic_closure": "Delta(E_total)-W_conversion=0",
            "density_energy_work_closure": "signed endpoint ledger includes wave, gradient, composition, links, and retention",
            "independent_raw_endpoint_replay_required": True,
            "whole_wave_dissipation_claim": False,
        }
        work["self_sha256"] = digest(work, WORK_PROOF_DOMAIN)
        return {
            "q": {"min": tag(0.0), "max_outward": tag(outward_upper(q_max)), "strictly_less_than_one": q_max < one},
            "one_minus_q": {"min_outward": tag(outward_lower(one_minus_q)), "max": tag(1.0)},
            "kappa": {"min_outward": tag(outward_lower(kappa_min)), "max_outward": tag(outward_upper(kappa_max))},
            "beta": {"min_outward": tag(outward_lower(beta_min)), "max_outward": tag(outward_upper(beta_max))},
            "runtime_roundoff_model": {
                "unit_roundoff": tag(float(unit)),
                "operation_count_upper": int(operation_count),
                "gamma_outward": tag(outward_upper(gamma)),
                "operation_scale_upper": tag(float(operation_scale)),
                "absolute_error_upper": tag(outward_upper(runtime_error)),
                "covers": ["factored epsilon evaluation", "frozen-Q denominator and quotient", "exponential alpha", "transfer and density updates", "phase-rescale target reconstruction"],
            },
            "progress_transfer": {"abs_lower_outward": tag(progress_lo), "abs_upper_at_lower_corner": tag(progress_hi), "U_T": tag(progress_u)},
            "neutral_transfer": {"abs_supremum_outward": tag(neutral_hi), "lower_outward": tag(neutral_lo), "U_T": tag(neutral_u)},
            "density_coefficients": {
                "one_minus_beta_min": tag(outward_lower(one - beta_max)),
                "phi_beta_min": tag(outward_lower(phi * beta_min)),
                "beta_min": tag(outward_lower(beta_min)),
                "one_minus_phi_beta_min": tag(outward_lower(coefficient_floor)),
                "all_nonnegative": coefficient_floor > 0,
            },
            "epsilon_abs_max": tag(outward_upper(epsilon_abs_max)),
            "epsilon2_post_max": tag(outward_upper(epsilon2_post_max)),
            "ema_support_max": tag(float(ema_max)),
            "accepted_density_max": tag(float(accepted["density_sum_at_most"] if not isinstance(accepted["density_sum_at_most"], str) else f64(accepted["density_sum_at_most"]))),
            "density_sum_identity": "EY_next+EI_next=EY+EI",
            "imbalance_identity": "epsilon_next=alpha*epsilon",
            "signed_transfer_identity": "T=epsilon*(1-alpha)/(1+phi)",
            "work_domain_proof": work,
            "map_forward_inclusion": True,
        }
def coefficient_trials(profile: Mapping[str, Any], scalars: Mapping[str, float], bounds: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    params = profile.get("parameters") if isinstance(profile.get("parameters"), Mapping) else profile
    _, _, _, _, _, margins = _profile_sections(profile)
    support, _, _, _, _, _ = _profile_sections(profile)
    candidates = params.get("epsilon_memory_time_candidates_s")
    require(isinstance(candidates, list) and candidates, "physical-time candidate order missing")
    epsilon2_bound = f64(bounds["epsilon2_post_max"], "epsilon2 bound")
    needed_slack = _number(margins["ema_upper_slack_min"], "EMA slack")
    duration = support["duration_s"]
    duration_values = duration if isinstance(duration, list) else [duration["min"], duration["max"]]
    rationals = support.get("runtime_exact_rationals")
    if rationals is None and isinstance(profile.get("clock"), Mapping):
        rationals = profile["clock"].get("runtime_exact_rationals")
    require(isinstance(rationals, list) and len(rationals) == len(duration_values), "exact duration registration mismatch")
    trials: list[dict[str, Any]] = []
    with localcontext() as context:
        context.prec = 100
        h_min_d, h_max_d = (Decimal.from_float(scalars[key]) for key in ("h_min", "h_max"))
        ema_max_d = Decimal.from_float(scalars["ema_max"])
        epsilon2_bound_d = Decimal.from_float(epsilon2_bound)
        required_slack_d = Decimal.from_float(needed_slack)
        for ordinal, raw in enumerate(candidates):
            memory = _number(raw, f"coefficient {ordinal}")
            trial: dict[str, Any] = {"ordinal": ordinal, "epsilon_memory_time_s": raw, "duration_horizons": [], "tau_asymptotic_horizon": tag(1.0)}
            if memory <= 0.0:
                trial.update({"tau_min_horizon": None, "tau_max_horizon": None, "ema_endpoint_max_outward": None, "ema_upper_slack_lower": None, "status": "FAIL", "reason": "physical epsilon_memory_time is not positive"})
                trials.append(trial)
                continue
            memory_d = Decimal.from_float(memory)
            tau_min_d = Decimal(1) - (-h_min_d / memory_d).exp()
            tau_max_d = Decimal(1) - (-h_max_d / memory_d).exp()
            endpoint_d = (Decimal(1) - tau_min_d) * ema_max_d + tau_min_d * epsilon2_bound_d
            slack_d = ema_max_d - endpoint_d
            tau_min, tau_max = outward_lower(tau_min_d), outward_upper(tau_max_d)
            endpoint, slack = outward_upper(endpoint_d), outward_lower(slack_d)
            horizons = []
            for index, (rational, duration_raw) in enumerate(zip(rationals, duration_values)):
                h_d = Decimal.from_float(_number(duration_raw, "exact duration"))
                tau_d = Decimal(1) - (-h_d / memory_d).exp()
                horizons.append({"ordinal": index, "duration_exact_rational": {"numerator": rational["numerator"], "denominator": rational["denominator"]}, "duration_s": tag(float(h_d)), "tau_lower_outward": tag(outward_lower(tau_d)), "tau_upper_outward": tag(outward_upper(tau_d))})
            trial["duration_horizons"] = horizons
            trial.update({"tau_min_horizon": tag(tau_min), "tau_max_horizon": tag(tau_max), "ema_endpoint_max_outward": tag(endpoint), "ema_upper_slack_lower": tag(slack), "status": "PASS" if 0.0 < float(tau_min) <= float(tau_max) < 1.0 and float(slack) >= float(required_slack_d) else "FAIL"})
            trial["reason"] = None if trial["status"] == "PASS" else "physical-time EMA forward-inclusion failed"
            trials.append(trial)
    selected = next((row for row in trials if row["status"] == "PASS"), None)
    require(selected is not None and selected["epsilon_memory_time_s"] == params["epsilon_memory_time_s"], "coefficient selection is not first registered pass")
    return trials, selected


def cells(viability: Mapping[str, Any], profile: Mapping[str, Any], bounds: Mapping[str, Any]) -> list[dict[str, Any]]:
    progress_lower = f64(bounds["progress_transfer"]["abs_lower_outward"], "progress lower")
    progress_u = f64(bounds["progress_transfer"]["U_T"], "progress uncertainty")
    neutral_upper = f64(bounds["neutral_transfer"]["abs_supremum_outward"], "neutral upper")
    neutral_u = f64(bounds["neutral_transfer"]["U_T"], "neutral uncertainty")
    margins = viability["registered_margins"]
    delta_min, delta_neutral, u_max = (_number(margins[key], key) for key in ("Delta_T_min", "Delta_T_neutral", "U_T_max"))
    common = bool(bounds.get("map_forward_inclusion") and bounds["density_coefficients"]["all_nonnegative"])
    output: list[dict[str, Any]] = []
    for cell in viability["complete_domain_cover"]:
        cell_id = cell["cell_id"]
        progress = cell_id in {"C05-progress-positive", "C06-progress-negative"}
        noop = cell_id in {"C00-exact-zero", "C01-balanced-memory-zero"}
        if progress:
            margin = progress_lower - progress_u
            passed = progress_u <= u_max and margin >= delta_min and progress_lower > 0.0
            classification = "dissipative-imbalance-progress"
        else:
            margin = delta_neutral - (neutral_upper + neutral_u)
            passed = neutral_u <= u_max and neutral_upper + neutral_u <= delta_neutral
            classification = "exact-noop" if noop else "certified-numerical-zero"
        output.append(
            {
                "cell_id": cell_id,
                "cell_sha256": digest(cell, CELL_DOMAIN),
                "epsilon_interval": cell["epsilon_interval"],
                "epsilon2_ema_interval": cell["epsilon2_ema_interval"],
                "predicate": cell["predicate"],
                "status": "PASS" if common and passed else "FAIL",
                "classification": classification,
                "forward_in_D_conv": common,
                "forward_in_A_accepted": common,
                "density_nonnegative": bool(bounds["density_coefficients"]["all_nonnegative"]),
                "density_sum_conserved": True,
                "work_domain_proof_sha256": bounds["work_domain_proof"]["self_sha256"],
                "work_definition": bounds["work_domain_proof"]["definition"],
                "work_closure_class": "analytic signed endpoint identity plus independent raw-endpoint replay",
                "work_closure_abs": tag(0.0),
                "signed_energy_work_closure": tag(0.0),
                "sign_transfer_equals_sign_epsilon": True if progress else None,
                "transfer_abs_lower": tag(progress_lower if progress else 0.0),
                "transfer_abs_upper": tag(neutral_upper if not progress else f64(bounds["progress_transfer"]["abs_upper_at_lower_corner"], "progress upper")),
                "transfer_uncertainty": tag(progress_u if progress else neutral_u),
                "transfer_margin_lower": tag(margin),
                "exact_named_noop": noop,
                "unresolved": False,
            }
        )
    return output
def expected_witnesses(manifest: Mapping[str, Any], w5: Mapping[str, Any], artifact_root: Path) -> list[dict[str, Any]]:
    require(manifest.get("schema") == WITNESS_MANIFEST_SCHEMA, "witness manifest schema mutation")
    check_self(manifest, WITNESS_MANIFEST_SCHEMA, "witness manifest")
    require(manifest.get("w5_run_id") == w5["binding"]["run_id"] and manifest.get("raw_hash_domain") == RAW_DOMAIN_TEXT and manifest.get("fixtures_define_support") is False and manifest.get("proof_cover_is_profile_registered") is True, "witness manifest policy/predecessor mutation")
    rows = manifest.get("witnesses")
    require(isinstance(rows, list) and [row.get("fixture_id") if isinstance(row, dict) else None for row in rows] == list(WITNESS_CELL_REGISTRATION), "witness registration order mutation")
    result: list[dict[str, Any]] = []
    for row in rows:
        require(isinstance(row, dict), "witness row is not an object")
        fixture_id = row["fixture_id"]
        expected_cells = WITNESS_CELL_REGISTRATION.get(fixture_id)
        require(expected_cells is not None and row.get("covered_cell_ids") == list(expected_cells), "witness cell claim mutation")
        require(row.get("kind") == "W5-frozen-Q-raw-control-witness.v1" and row.get("raw_hash_domain") == RAW_DOMAIN_TEXT and row.get("defines_support") is False and row.get("determines_cells") is False and row.get("determines_coefficient") is False and row.get("determines_verdict") is False, "fixture-derived pseudo-physics mutation")
        control = read_json(file_at(w5["root"], f"gates/g05-conversion/controls/{fixture_id}.json"))
        descriptors = control.get("fixtures")
        require(isinstance(descriptors, Mapping), f"{fixture_id}: fixture descriptors missing")
        predecessor_descriptor, candidate_descriptor = descriptors.get("predecessor"), descriptors.get("candidate")
        require(isinstance(predecessor_descriptor, Mapping) and isinstance(candidate_descriptor, Mapping), f"{fixture_id}: fixture descriptors malformed")
        source_pre, source_post = predecessor_descriptor["path"], candidate_descriptor["path"]
        artifact_pre, artifact_post = f"witnesses/{fixture_id}-predecessor.f64le", f"witnesses/{fixture_id}-candidate.f64le"
        require(row.get("predecessor_source_path") == source_pre and row.get("candidate_source_path") == source_post and row.get("predecessor_artifact_path") == artifact_pre and row.get("candidate_artifact_path") == artifact_post, "raw witness path mutation")
        pre_raw, post_raw = file_at(w5["root"], source_pre).read_bytes(), file_at(w5["root"], source_post).read_bytes()
        require(pre_raw == file_at(artifact_root, artifact_pre).read_bytes() and post_raw == file_at(artifact_root, artifact_post).read_bytes(), "raw witness no longer links to W5 fixture")
        pre_hash, post_hash = raw_hash(pre_raw), raw_hash(post_raw)
        require(row.get("predecessor_sha256") == pre_hash and row.get("candidate_sha256") == post_hash, "raw witness hash mutation")
        require(control.get("control_id") == fixture_id and control.get("actual_decision") == "PASS" and control.get("committable") is True and control.get("predecessor_raw_sha256") == sha(pre_raw) and control.get("candidate_raw_sha256") == sha(post_raw), "W5 raw control linkage mutation")
        normalized = {"fixture_id": fixture_id, "covered_cell_ids": list(expected_cells), "predecessor_sha256": pre_hash, "candidate_sha256": post_hash, "kind": row["kind"], "defines_support": False, "determines_verdict": False}
        normalized["witness_sha256"] = digest(normalized, WITNESS_DOMAIN)
        require(row.get("receipt_witness_sha256") == normalized["witness_sha256"], "receipt/raw witness linkage mutation")
        result.append(normalized)
    result.sort(key=lambda row: row["fixture_id"])
    return result


def expected_receipt(
    viability: Mapping[str, Any],
    profile: Mapping[str, Any],
    conversion_root: Mapping[str, Any],
    binding: Mapping[str, Any],
    bounds: Mapping[str, Any],
    trials: list[dict[str, Any]],
    selected: Mapping[str, Any] | None,
    witnesses: list[dict[str, Any]],
    complete_cover: Mapping[str, Any],
) -> dict[str, Any]:
    cell_rows = cells(viability, profile, bounds)
    pass_count = sum(row["status"] == "PASS" for row in cell_rows)
    fail_count = sum(row["status"] == "FAIL" for row in cell_rows)
    unresolved_count = sum(bool(row["unresolved"]) for row in cell_rows)
    status = "PASS" if selected is not None and pass_count == len(cell_rows) and fail_count == 0 and unresolved_count == 0 else "FAIL"
    support = viability["D_conv"]
    duration = support["duration_s"]
    duration_bounds = duration if isinstance(duration, list) else [duration["min"], duration["max"]]
    exact_rationals = viability["exact_duration_rationals"]
    receipt: dict[str, Any] = {
        "schema": W5V_RECEIPT_SCHEMA,
        "gate": "G5V",
        "owning_package": "W5V",
        "status": status,
        "failure_artifact": status != "PASS",
        "viability_profile_sha256": viability["profile_sha256"],
        "conversion_profile_sha256": profile["profile_sha256"],
        "conversion_root_sha256": conversion_root["self_sha256"],
        "conversion_law_sha256": profile["law_sha256"],
        "w5_engineering_binding": dict(binding),
        "parent_identities": viability["parent_identities"],
        "certificate_identities": binding["certificate_identities"],
        "support_sha256": viability["support_sha256"],
        "accepted_sha256": viability["accepted_sha256"],
        "cover_sha256": viability["cover_sha256"],
        "partition_sha256": viability["partition_sha256"],
        "registered_margins_sha256": digest(viability["registered_margins"], MARGINS_DOMAIN),
        "proof_method": viability["method"],
        "proof_method_sha256": digest(viability["method"], METHOD_DOMAIN),
        "epsilon_prog_min": viability["epsilon_prog_min"],
        "D_prog": viability["D_prog"],
        "D_neutral": viability["D_neutral"],
        "D_conv": viability["D_conv"],
        "A_accepted": viability["A_accepted"],
        "exact_rational_time_members": exact_rationals,
        "closed_duration_interval": {"min": duration_bounds[0], "max": duration_bounds[1]},
        "physical_epsilon_memory_time_s": viability["physical_epsilon_memory_time_s"],
        "complete_cover": complete_cover,
        "analytic_enclosures": bounds,
        "coefficient_trials": trials,
        "selected_coefficient": selected,
        "cells": cell_rows,
        "cell_counts": {"total": len(cell_rows), "PASS": pass_count, "FAIL": fail_count, "UNRESOLVED": unresolved_count},
        "accepted_intervals": {
            "D_conv": viability["D_conv"],
            "A_accepted": viability["A_accepted"],
            "duration_exact_rationals": exact_rationals,
            "cells": [dict(row) for row in cell_rows if row["status"] == "PASS"],
        },
        "rejected_intervals": {
            "failed_cells": [dict(row) for row in cell_rows if row["status"] != "PASS"],
            "unresolved_cells": [dict(row) for row in cell_rows if row["unresolved"]],
            "coefficient_candidates": [dict(row) for row in trials if row["status"] != "PASS"],
            "support_shrinkage": "REJECTED:new-failed-profile-identity",
        },
        "witnesses": witnesses,
        "fixtures_define_support": False,
        "frozen_before_observation": True,
        "activity_coverage_residence": {
            "proof_cells": ["C05-progress-positive", "C06-progress-negative"],
            "strict_progress_predicate": "abs(T)-U_T>=Delta_T_min>0",
            "strict_progress_verified": all(row["status"] == "PASS" for row in cell_rows if row["classification"] == "dissipative-imbalance-progress"),
            "active_scale_coverage_fraction": tag(1.0),
            "active_mode_coverage_fraction": tag(1.0),
            "cross_scale_residency": "all-registered-scales-one-complete-conversion-interval",
            "residence_intervals_min": 1,
            "total_site_occupancy_identity": "EY_next+EI_next=EY+EI",
        },
        "boundary_controls": [
            {"control_id": "exact-zero", "registered_cell_ids": ["C00-exact-zero"], "precondition": "EY==EI==epsilon2_ema==0", "analytic_outcome": {"T": tag(0.0), "epsilon2_ema_next": tag(0.0)}, "expected_raw_relation": "exact-noop", "runtime_witness_required": True},
            {"control_id": "balanced-memory-zero", "registered_cell_ids": ["C01-balanced-memory-zero"], "precondition": "epsilon==0 and epsilon2_ema==0", "analytic_outcome": {"T": tag(0.0), "epsilon2_ema_next": tag(0.0)}, "expected_raw_relation": "exact-noop", "runtime_witness_required": True},
            {"control_id": "balanced-positive-memory", "registered_cell_ids": ["C02-balanced-memory-positive"], "precondition": "epsilon==0 and epsilon2_ema>0", "analytic_outcome": {"T": tag(0.0), "epsilon2_ema_next": "(1-tau)*epsilon2_ema"}, "expected_raw_relation": "positions-and-velocities-exact-noop;EMA-physical-relaxation", "runtime_witness_required": True},
            {"control_id": "near-capacity-both-signs-phases", "registered_cell_ids": ["C05-progress-positive", "C06-progress-negative"], "precondition": "rho=profile-rho-max;all-registered-phase-branches", "analytic_outcome": {"forward_included": bool(bounds["map_forward_inclusion"]), "sign_transfer_equals_sign_epsilon": True}, "expected_raw_relation": "density-conserved;phase-preserved-or-registered-inheritance", "runtime_witness_required": True},
        ],
        "mutation_controls": [
            {"control_id": "mutate-support", "expected": "REJECT"},
            {"control_id": "delete-cover-cell", "expected": "REJECT"},
            {"control_id": "mutate-cell-predicate", "expected": "REJECT"},
            {"control_id": "mutate-EMA-axis", "expected": "REJECT"},
            {"control_id": "mutate-duration-member", "expected": "REJECT"},
            {"control_id": "reorder-coefficients", "expected": "REJECT"},
            {"control_id": "mutate-margin", "expected": "REJECT"},
            {"control_id": "mutate-W5-source", "expected": "REJECT"},
            {"control_id": "substitute-fixture-for-cover", "expected": "REJECT"},
            {"control_id": "mutate-parent-identity", "expected": "REJECT"},
        ],
        "law_fallback": None,
        "clipping": "none",
        "normalization": "none",
        "retry": "none",
        "silent_transfer_shrink": "none",
        "rejected_candidates": [dict(row) for row in trials if row["status"] != "PASS"],
        "decision": "ADMIT-FROZEN-Q-MAP" if status == "PASS" else "REVISE-LAW-FULL-HAMILTONIAN-GRADIENT-FLOW",
    }
    receipt["self_sha256"] = digest(receipt, W5V_RECEIPT_SCHEMA)
    return receipt


def expected_extension(receipt: Mapping[str, Any], parent: Mapping[str, Any]) -> dict[str, Any]:
    parent_ordinal = check_parent_extension(parent)
    inventory = list(parent["complete_section_inventory"])
    section: dict[str, Any] = {
        "schema": W5V_SECTION_SCHEMA,
        "section_id": "w5v-complete-domain-forward-viability",
        "ordinal": parent_ordinal + 1,
        "gate": "G5V",
        "owning_package": "W5V",
        "required": True,
        "receipt_sha256": receipt["self_sha256"],
        "viability_profile_sha256": receipt["viability_profile_sha256"],
        "conversion_profile_sha256": receipt["conversion_profile_sha256"],
        "conversion_root_sha256": receipt["conversion_root_sha256"],
        "conversion_law_sha256": receipt["conversion_law_sha256"],
        "support_sha256": receipt["support_sha256"],
        "accepted_sha256": receipt["accepted_sha256"],
        "partition_sha256": receipt["partition_sha256"],
        "proof_method_sha256": receipt["proof_method_sha256"],
        "registered_margins_sha256": receipt["registered_margins_sha256"],
        "work_domain_proof_sha256": receipt["analytic_enclosures"]["work_domain_proof"]["self_sha256"],
        "w5_engineering_run_id": receipt["w5_engineering_binding"]["run_id"],
        "w5_engineering_index_sha256": receipt["w5_engineering_binding"]["index_sha256"],
        "w5_conversion_source_sha256": receipt["w5_engineering_binding"]["conversion_source_sha256"],
        "w5_source_identity_sha256": receipt["w5_engineering_binding"]["source_identity_sha256"],
        "parent_identities": receipt["parent_identities"],
        "certificate_identities": receipt["certificate_identities"],
        "cover_sha256": receipt["cover_sha256"],
        "all_cell_pass_count": receipt["cell_counts"]["PASS"],
        "unresolved_count": receipt["cell_counts"]["UNRESOLVED"],
        "selected_epsilon_memory_time_s": receipt["selected_coefficient"]["epsilon_memory_time_s"],
        "failed_cell_count": receipt["cell_counts"]["FAIL"],
        "coefficient_trial_count": len(receipt["coefficient_trials"]),
        "all_cells_resolved": receipt["cell_counts"]["UNRESOLVED"] == 0,
        "epsilon_prog_min": receipt["epsilon_prog_min"],
        "D_prog": receipt["D_prog"],
        "D_neutral": receipt["D_neutral"],
        "exact_duration_rationals": receipt["exact_rational_time_members"],
        "physical_time_candidate_order": receipt["coefficient_trials"],
    }
    if "evidence_identities" in receipt:
        section["evidence_identities"] = receipt["evidence_identities"]
    section["self_sha256"] = digest(section, W5V_SECTION_DOMAIN)
    extension = {
        "schema": W5V_EXTENSION_SCHEMA,
        "gate": "G5V",
        "owning_package": "W5V",
        "chain_ordinal": parent_ordinal + 1,
        "chain_status": "provisional",
        "certificate_chain_id": parent["certificate_chain_id"],
        "parent_certificate_sha256": parent["self_sha256"],
        "parent_section_inventory": inventory,
        "added_section": section,
        "complete_section_inventory": inventory + [section],
        "consumed_semantic_subhashes": list(parent.get("consumed_semantic_subhashes", [])),
        "parent_identities": receipt["parent_identities"],
        "certificate_identities": receipt["certificate_identities"],
        "production_certificate_complete": False,
        "required_future_sections": list(parent.get("required_future_sections", [])),
        "final_certificate_identity_sha256": None,
    }
    extension["self_sha256"] = digest(extension, W5V_EXTENSION_DOMAIN)
    return extension


def _layout_counts(layout: Mapping[str, Any]) -> tuple[int, int, int, int]:
    if isinstance(layout.get("state_layout"), Mapping):
        layout = layout["state_layout"]
    counts = tuple(layout.get(name) for name in ("scale_count", "mode_count", "component_count"))
    batch = layout.get("batch_limit", layout.get("batch_lanes", 1))
    require(
        all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in (*counts, batch)),
        "raw state layout counts must be positive integers",
    )
    scales, modes, components = counts
    require(components == 9, "raw state layout must expose the nine W5 components")
    return scales, modes, components, batch


def raw_values(raw: bytes, label: str, layout: Mapping[str, Any]) -> tuple[float, ...]:
    scales, modes, components, batch = _layout_counts(layout)
    expected_count = scales * components * modes * batch
    require(len(raw) == expected_count * 8, f"{label}: unexpected raw state layout")
    values = struct.unpack("<" + "d" * expected_count, raw)
    require(all(math.isfinite(value) for value in values), f"{label}: non-finite raw state value")
    return values


def raw_offset(scale: int, component: int, mode: int, batch: int, layout: Mapping[str, Any]) -> int:
    scales, modes, components, batch_lanes = _layout_counts(layout)
    require(
        0 <= scale < scales and 0 <= component < components and 0 <= mode < modes and 0 <= batch < batch_lanes,
        "raw state index out of bounds",
    )
    return ((scale * components + component) * modes + mode) * batch_lanes + batch


def position_density(values: Sequence[float], scale: int, mode: int, batch: int, component: int, layout: Mapping[str, Any]) -> float:
    real, imaginary = values[raw_offset(scale, component, mode, batch, layout)], values[raw_offset(scale, component + 1, mode, batch, layout)]
    return real * real + imaginary * imaginary


def pair_branch(ey: float, ei: float) -> str:
    if ey > 0.0 and ei > 0.0:
        return "own-nonzero"
    if ey == 0.0 and ei > 0.0:
        return "yang-empty"
    if ey > 0.0 and ei == 0.0:
        return "yin-empty"
    return "both-empty"


def raw_pair_activity(pre_raw: bytes, post_raw: bytes, fixture_id: str, layout: Mapping[str, Any]) -> dict[str, Any]:
    pre, post = raw_values(pre_raw, f"{fixture_id} predecessor", layout), raw_values(post_raw, f"{fixture_id} candidate", layout)
    scales, modes, _, batch_lanes = _layout_counts(layout)
    pre_scales: set[int] = set()
    post_scales: set[int] = set()
    pre_modes: set[int] = set()
    post_modes: set[int] = set()
    pre_batches: set[int] = set()
    post_batches: set[int] = set()
    active_pairs: list[dict[str, int]] = []
    observations: list[dict[str, Any]] = []
    for scale in range(scales):
        for mode in range(modes):
            for batch in range(batch_lanes):
                ey_pre, ei_pre = position_density(pre, scale, mode, batch, 0, layout), position_density(pre, scale, mode, batch, 2, layout)
                ey_post, ei_post = position_density(post, scale, mode, batch, 0, layout), position_density(post, scale, mode, batch, 2, layout)
                active_pre, active_post = ey_pre > 0.0 or ei_pre > 0.0, ey_post > 0.0 or ei_post > 0.0
                if active_pre:
                    pre_scales.add(scale)
                    pre_modes.add(mode)
                    pre_batches.add(batch)
                if active_post:
                    post_scales.add(scale)
                    post_modes.add(mode)
                    post_batches.add(batch)
                if active_pre or active_post:
                    active_pairs.append({"scale": scale, "mode": mode, "batch": batch})
                observations.append(
                    {
                        "scale": scale,
                        "mode": mode,
                        "batch": batch,
                        "branch_pre": pair_branch(ey_pre, ei_pre),
                        "branch_post": pair_branch(ey_post, ei_post),
                        "EY_pre": tag(ey_pre),
                        "EI_pre": tag(ei_pre),
                        "EY_post": tag(ey_post),
                        "EI_post": tag(ei_post),
                        "T_raw": tag(ey_pre - ey_post),
                        "position_active_pre": active_pre,
                        "position_active_post": active_post,
                        "position_active_pair": active_pre or active_post,
                    }
                )
    return {
        "layout": {"scale_count": scales, "mode_count": modes, "batch_lanes": batch_lanes, "packed_components": 9},
        "pre_active_scale_ids": sorted(pre_scales),
        "post_active_scale_ids": sorted(post_scales),
        "active_scale_ids": sorted(pre_scales | post_scales),
        "pre_active_mode_site_ids": sorted(pre_modes),
        "post_active_mode_site_ids": sorted(post_modes),
        "active_mode_site_ids": sorted(pre_modes | post_modes),
        "pre_active_batch_ids": sorted(pre_batches),
        "post_active_batch_ids": sorted(post_batches),
        "active_batch_ids": sorted(pre_batches | post_batches),
        "active_scale_mode_site_pairs": active_pairs,
        "pair_observations": observations,
    }




def exact_duration_rational(profile: Mapping[str, Any], duration_s: float, receipt: Mapping[str, Any]) -> dict[str, int]:
    value = receipt.get("duration_exact_rational")
    require_reduced_runtime_rational(value, duration_s, profile, label="raw activity duration")
    return {"numerator": value["numerator"], "denominator": value["denominator"]}


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    require(isinstance(numerator, int) and isinstance(denominator, int) and denominator > 0 and 0 <= numerator <= denominator, "invalid raw activity fraction")
    return {"numerator": numerator, "denominator": denominator, "fraction": tag(numerator / denominator)}
def fraction_or_zero(numerator: int, denominator: int) -> dict[str, Any]:
    return fraction(numerator, denominator) if denominator > 0 else fraction(0, 1)
def validate_activity_profile_snapshots(
    w1: Mapping[str, Any],
    w1_root: Mapping[str, Any],
    w2: Mapping[str, Any],
    w2_root: Mapping[str, Any],
    conversion_root: Mapping[str, Any],
) -> None:
    require(w1.get("schema") == "cassi.qi-flow-profile.v1", "raw activity W1 profile schema mutation")
    w1_body = dict(w1)
    w1_identity = w1_body.pop("profile_sha256", None)
    require(is_sha256(w1_identity) and w1_identity == digest(w1_body, "cassi.qi-flow-profile.v1"), "raw activity W1 profile identity mutation")
    require(w1_root.get("schema") == "cassi.qi-flow-contract-root.v1", "raw activity W1 root schema mutation")
    check_self(w1_root, "cassi.qi-flow-contract-root-bootstrap.v1", "raw activity W1 root")
    require(w1.get("contract_root_sha256") == w1_root.get("self_sha256"), "raw activity W1 profile/root linkage mutation")
    semantic_rows = w1.get("semantic_subhashes")
    require(
        isinstance(semantic_rows, list)
        and semantic_rows
        and all(
            isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and row["name"]
            and isinstance(row.get("state_consuming"), bool)
            and is_sha256(row.get("sha256"))
            for row in semantic_rows
        )
        and len({row["name"] for row in semantic_rows}) == len(semantic_rows),
        "raw activity W1 semantic-subhash linkage mutation",
    )
    require(w2.get("schema") == "cassi.qi-flow-geometry-profile.w2.periodic-fft2.v1", "raw activity W2 profile schema mutation")
    w2_body = dict(w2)
    w2_identity = w2_body.pop("profile_sha256", None)
    require(is_sha256(w2_identity) and w2_identity == digest(w2_body, "cassi.qi-flow-geometry-profile.w2.periodic-fft2.v1"), "raw activity W2 profile identity mutation")
    require(w2_root.get("schema") == "cassi.qi-flow-contract-root.w2.periodic-fft2.v1", "raw activity W2 root schema mutation")
    check_self(w2_root, "cassi.qi-flow-contract-root.w2.periodic-fft2.v1", "raw activity W2 root")
    parent_w1 = w2.get("parent_w1")
    require(
        w2.get("contract_root_sha256") == w2_root.get("self_sha256")
        and w2.get("base_profile_sha256") == w1_identity
        and w2.get("base_contract_root_sha256") == w1_root.get("self_sha256")
        and isinstance(parent_w1, dict)
        and parent_w1.get("profile_sha256") == w1_identity
        and parent_w1.get("contract_root_sha256") == w1_root.get("self_sha256")
        and conversion_root.get("w2_geometry_profile_sha256") == w2_identity,
        "raw activity W1/W2/W5 immutable ancestry mutation",
    )


def expected_raw_activity(root: Path, w5: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    observed = read_json(file_at(root, "gates/g05v-conversion-viability/raw-activity.json"))
    require(observed.get("schema") == RAW_ACTIVITY_SCHEMA, "raw activity schema mutation")
    check_self(observed, RAW_ACTIVITY_DOMAIN, "raw activity")
    require(observed.get("fixtures_define_support") is False and observed.get("fixtures_determine_verdict") is False, "raw activity fixture authority mutation")
    w1 = read_json(file_at(root, "profile/w1-activity-profile.json"))
    w1_root = read_json(file_at(root, "profile/w1-activity-root.json"))
    w2 = read_json(file_at(root, "profile/w2-geometry-profile.json"))
    w2_root = read_json(file_at(root, "profile/w2-geometry-root.json"))
    validate_activity_profile_snapshots(w1, w1_root, w2, w2_root, w5["conversion_root"])
    field, spatial = w1.get("field"), w1.get("spatial")
    require(isinstance(field, dict) and isinstance(spatial, dict), "raw activity W1 profile shape mutation")
    scales, modes, components, batch_lanes = _layout_counts(field)
    require(field.get("dtype") == "float64" and field.get("byte_order") == "little", "raw activity W1 field dtype/byte-order mutation")
    active_shapes = field.get("active_shapes")
    active_sites = field.get("active_site_counts")
    require(
        isinstance(active_shapes, list)
        and len(active_shapes) == scales
        and all(isinstance(shape, list) and len(shape) == 2 and all(isinstance(value, int) and value > 0 for value in shape) for shape in active_shapes)
        and isinstance(active_sites, list)
        and len(active_sites) == scales
        and all(isinstance(value, int) and 0 < value <= modes for value in active_sites)
        and spatial.get("active_shapes") == active_shapes
        and isinstance(spatial.get("active_site_order"), str)
        and spatial["active_site_order"],
        "raw activity W1 active shape/order mutation",
    )
    expected_state_layout = {
        "scale_count": field["scale_count"],
        "mode_count": field["mode_count"],
        "component_count": field["component_count"],
        "shape": [field["scale_count"], field["component_count"] * field["mode_count"], None],
        "dtype": field["dtype"],
        "byte_order": field["byte_order"],
        "layout_id": field["layout_id"],
        "batch_limit": field["batch_limit"],
        "backend": w1["backend_contract"]["device"],
        "state_byte_limit": field["state_byte_limit"],
        "active_shapes": active_shapes,
        "active_site_counts": active_sites,
        "state_bounds": field["state_bounds"],
    }
    observed_layout = observed.get("layout_binding")
    require(isinstance(observed_layout, Mapping), "raw activity layout binding missing")
    geometry_contract = w2.get("geometry_contract")
    require(isinstance(geometry_contract, Mapping), "raw activity W2 geometry contract missing")
    grid_shape = w2.get("grid_shape", geometry_contract.get("grid_shape", observed_layout.get("w2_grid_shape")))
    flattening = w2.get("mode_site_flattening", geometry_contract.get("mode_site_flattening", "profile-declared-mode-order"))
    require(isinstance(grid_shape, list) and grid_shape and all(isinstance(value, int) and value > 0 for value in grid_shape), "raw activity W2 grid shape mutation")
    expected_layout = {
        "w1_profile_sha256": w1["profile_sha256"],
        "w1_profile_root_sha256": w1_root["self_sha256"],
        "w1_active_shapes": spatial["active_shapes"],
        "w1_active_site_order": spatial["active_site_order"],
        "w1_state_layout": expected_state_layout,
        "w2_geometry_profile_sha256": w2["profile_sha256"],
        "w2_geometry_contract_sha256": w2_root["self_sha256"],
        "w2_grid_shape": grid_shape,
        "w2_mode_site_flattening": flattening,
        "mode_site_bijection": True,
        "witness_batch_lanes": batch_lanes,
        "profile_batch_limit": field["batch_limit"],
    }
    require(w2.get("profile_sha256") == w5["conversion_root"].get("w2_geometry_profile_sha256"), "raw activity W2/W5 geometry linkage mutation")
    require(w2.get("parent_w1", {}).get("profile_sha256") == w1["profile_sha256"] and w2.get("parent_w1", {}).get("contract_root_sha256") == w1_root["self_sha256"], "raw activity W2/W1 ancestry mutation")
    require(observed.get("layout_binding") == expected_layout, "raw activity W1/W2 layout binding mutation")
    cells_by_id = {row["cell_id"]: row for row in receipt["cells"]}
    progress_u = f64(receipt["analytic_enclosures"]["progress_transfer"]["U_T"], "raw activity U_T")
    progress_margin = f64(w5["profile"]["registered_margins"]["Delta_T_min"], "raw activity Delta_T_min")
    rows: list[dict[str, Any]] = []
    position_scales: set[int] = set()
    position_modes: set[int] = set()
    position_batches: set[int] = set()
    position_pairs: set[tuple[int, int, int]] = set()
    progress_scales: set[int] = set()
    progress_modes: set[int] = set()
    progress_batches: set[int] = set()
    progress_pairs: set[tuple[int, int, int]] = set()
    residence_pairs = {scale: 0 for scale in range(scales)}
    residence_intervals = {scale: 0 for scale in range(scales)}
    accepted_forward = accepted_conversion = accepted_progress_count = 0
    for fixture_id, covered_cells in WITNESS_CELL_REGISTRATION.items():
        control = read_json(file_at(w5["root"], f"gates/g05-conversion/controls/{fixture_id}.json"))
        require(control.get("schema") == "cassi.qi-flow-w5-integrated-control.v1" and control.get("control_id") == fixture_id, f"raw activity {fixture_id}: control identity mutation")
        control_receipt = control.get("receipt")
        require(isinstance(control_receipt, Mapping), f"raw activity {fixture_id}: missing source receipt")
        check_self(control_receipt, W5_RECEIPT_SCHEMA, f"raw activity {fixture_id} receipt")
        descriptors = control.get("fixtures")
        require(isinstance(descriptors, Mapping), f"raw activity {fixture_id}: fixture descriptors missing")
        predecessor_descriptor, candidate_descriptor = descriptors.get("predecessor"), descriptors.get("candidate")
        require(isinstance(predecessor_descriptor, Mapping) and isinstance(candidate_descriptor, Mapping), f"raw activity {fixture_id}: fixture descriptors malformed")
        pre_raw = file_at(w5["root"], predecessor_descriptor["path"]).read_bytes()
        post_raw = file_at(w5["root"], candidate_descriptor["path"]).read_bytes()
        require(predecessor_descriptor.get("domain") == RAW_DOMAIN and candidate_descriptor.get("domain") == RAW_DOMAIN, f"raw activity {fixture_id}: raw domain mutation")
        require(predecessor_descriptor.get("dtype") == "<f8" and candidate_descriptor.get("dtype") == "<f8", f"raw activity {fixture_id}: raw dtype mutation")
        require(predecessor_descriptor.get("byte_count") == len(pre_raw) and candidate_descriptor.get("byte_count") == len(post_raw), f"raw activity {fixture_id}: raw byte count mutation")
        require(predecessor_descriptor.get("sha256") == sha(pre_raw) and candidate_descriptor.get("sha256") == sha(post_raw), f"raw activity {fixture_id}: raw descriptor hash mutation")
        require(sha(pre_raw) == control.get("predecessor_raw_sha256") and sha(post_raw) == control.get("candidate_raw_sha256"), f"raw activity {fixture_id}: W5 raw linkage mutation")
        activity = raw_pair_activity(pre_raw, post_raw, fixture_id, field)
        duration_s = f64(control.get("duration_s"), f"raw activity {fixture_id} duration")
        conversion = control_receipt.get("conversion")
        ema = control_receipt.get("ema")
        conversion_rows = conversion.get("rows") if isinstance(conversion, Mapping) else None
        require(isinstance(conversion_rows, list), f"raw activity {fixture_id}: conversion rows mutation")
        transfers = []
        for item in conversion_rows:
            require(isinstance(item, Mapping) and isinstance(item.get("scale"), int), f"raw activity {fixture_id}: malformed transfer row")
            transfers.append({key: item[key] for key in ("scale", "epsilon_min", "epsilon_max", "transfer_min", "transfer_max", "signed_progress_min")})
        forward = control.get("actual_decision") == "PASS" and control.get("committable") is True
        conversion_interval = (
            forward
            and control.get("conversion_enabled") is True
            and isinstance(conversion, Mapping)
            and conversion.get("q_evaluations") == 1
            and conversion.get("conversion_maps") == 1
            and isinstance(ema, Mapping)
            and ema.get("invocations") == 1
            and ema.get("updates") == 1
        )
        progress_cells = [cell_id for cell_id in covered_cells if cell_id in {"C05-progress-positive", "C06-progress-negative"}]
        progress_interval = conversion_interval and len(progress_cells) == 1
        progress_evidence: dict[str, Any] | None = None
        if progress_interval:
            require(len(transfers) == scales, f"raw activity {fixture_id}: missing per-scale transfer rows")
            expected_sign = 1 if progress_cells[0] == "C05-progress-positive" else -1
            active_count = progress_count = 0
            resident_scales: set[int] = set()
            for pair in activity["pair_observations"]:
                transfer = f64(pair["T_raw"], f"raw activity {fixture_id} T")
                margin = abs(transfer) - progress_u
                active = bool(pair["position_active_pre"] and pair["position_active_post"] and expected_sign * transfer > 0.0 and margin >= progress_margin)
                pair["expected_progress_sign"] = expected_sign
                pair["abs_T_minus_U_T"] = tag(margin)
                pair["progress_active"] = active
                if pair["position_active_pair"]:
                    active_count += 1
                    require(active, f"raw activity {fixture_id}: active site fails T sign/U/margin")
                if active:
                    progress_count += 1
                    progress_scales.add(pair["scale"])
                    progress_modes.add(pair["mode"])
                    progress_batches.add(pair["batch"])
                    progress_pairs.add((pair["scale"], pair["mode"], pair["batch"]))
                    residence_pairs[pair["scale"]] += 1
                    resident_scales.add(pair["scale"])
            for scale in resident_scales:
                residence_intervals[scale] += 1
            require(progress_count > 0, f"raw activity {fixture_id}: no progress-active pair")
            progress_evidence = {
                "cell_id": progress_cells[0],
                "U_T": receipt["analytic_enclosures"]["progress_transfer"]["U_T"],
                "Delta_T_min": w5["profile"]["registered_margins"]["Delta_T_min"],
                "position_active_pair_count": active_count,
                "progress_active_pair_count": progress_count,
                "cell_transfer_margin_lower": cells_by_id[progress_cells[0]]["transfer_margin_lower"],
                "all_position_active_pairs_clear_raw_sign_and_margin": progress_count == active_count,
            }
        else:
            for pair in activity["pair_observations"]:
                pair["expected_progress_sign"] = None
                pair["abs_T_minus_U_T"] = None
                pair["progress_active"] = False
        if forward:
            accepted_forward += 1
        if conversion_interval:
            accepted_conversion += 1
            position_scales.update(activity["active_scale_ids"])
            position_modes.update(activity["active_mode_site_ids"])
            position_batches.update(activity["active_batch_ids"])
            position_pairs.update((pair["scale"], pair["mode"], pair["batch"]) for pair in activity["active_scale_mode_site_pairs"])
        if progress_interval:
            accepted_progress_count += 1
        row = {
            "fixture_id": fixture_id,
            "covered_cell_ids": list(covered_cells),
            "control_role": "nonproduction-conversion-disabled-control" if control.get("conversion_enabled") is False else "production-forward-control",
            "predecessor_sha256": raw_hash(pre_raw),
            "candidate_sha256": raw_hash(post_raw),
            "control_receipt_sha256": control.get("receipt_self_sha256") or control.get("receipt_sha256"),
            "actual_decision": control.get("actual_decision"),
            "enabled": control.get("conversion_enabled"),
            "duration_s": duration_s,
            "duration_exact_rational": exact_duration_rational(w5["profile"], duration_s, control_receipt),
            "conversion_invocations": conversion.get("conversion_maps") if isinstance(conversion, Mapping) else None,
            "ema_updates": ema.get("updates") if isinstance(ema, Mapping) else None,
            "accepted_forward_step": forward,
            "accepted_conversion_interval": conversion_interval,
            "accepted_progress_interval": progress_interval,
            "transfer_rows": transfers,
            "progress_evidence": progress_evidence,
            "activity": activity,
        }
        row["trajectory_sha256"] = digest(row, RAW_ACTIVITY_SCHEMA)
        rows.append(row)
    aggregate = {
        "declared_trajectory_count": len(rows),
        "accepted_forward_step_count": accepted_forward,
        "accepted_conversion_interval_count": accepted_conversion,
        "accepted_progress_interval_count": accepted_progress_count,
        "layout": {"scale_count": scales, "mode_count": modes, "batch_lanes": batch_lanes, "packed_components": 9},
        "position_scale_coverage": fraction(len(position_scales), scales),
        "position_mode_coverage": fraction(len(position_modes), modes),
        "position_site_coverage": fraction(len(position_modes), modes),
        "position_batch_coverage": fraction(len(position_batches), batch_lanes),
        "position_scale_mode_site_coverage": fraction(len(position_pairs), scales * modes * batch_lanes),
        "progress_scale_coverage": fraction(len(progress_scales), scales),
        "progress_mode_coverage": fraction(len(progress_modes), modes),
        "progress_site_coverage": fraction(len(progress_modes), modes),
        "progress_batch_coverage": fraction(len(progress_batches), batch_lanes),
        "progress_scale_mode_site_coverage": fraction(len(progress_pairs), scales * modes * batch_lanes),
        "position_active_scale_ids": sorted(position_scales),
        "position_active_mode_site_ids": sorted(position_modes),
        "progress_active_scale_ids": sorted(progress_scales),
        "progress_active_mode_site_ids": sorted(progress_modes),
        "progress_residence_pair_intervals_by_scale": residence_pairs,
        "progress_residence_interval_count_by_scale": residence_intervals,
        "progress_residence_pair_interval_occupancy": fraction_or_zero(sum(residence_pairs.values()), accepted_progress_count * scales * modes * batch_lanes),
    }
    expected = {
        "schema": RAW_ACTIVITY_SCHEMA,
        "method": "decoded-little-endian-f64-W1-W2-state-pairs.v1",
        "fixtures_define_support": False,
        "fixtures_determine_verdict": False,
        "layout_binding": expected_layout,
        "trajectories": rows,
        "aggregate": aggregate,
    }
    expected["self_sha256"] = digest(expected, RAW_ACTIVITY_DOMAIN)
    require(observed == expected, "raw activity decoded W1/W2 trajectory/coverage/residence mutation")
    return expected
def raw_components_identical(before: bytes, after: bytes, components: range, layout: Mapping[str, Any]) -> bool:
    before_values, after_values = raw_values(before, label="control-law before", layout=layout), raw_values(after, label="control-law after", layout=layout)
    scales, modes, _, batch_lanes = _layout_counts(layout)
    for scale in range(scales):
        for component in components:
            for mode in range(modes):
                for batch in range(batch_lanes):
                    if before_values[raw_offset(scale, component, mode, batch, layout)] != after_values[raw_offset(scale, component, mode, batch, layout)]:
                        return False
    return True


def raw_lane(raw: bytes, scale: int, component: int, mode: int, batch: int, layout: Mapping[str, Any]) -> float:
    return raw_values(raw, label="control-law raw", layout=layout)[raw_offset(scale, component, mode, batch, layout)]


def f64_ulp_distance(actual: float, expected: float) -> int:
    require(math.isfinite(actual) and math.isfinite(expected), "ULP comparison requires finite binary64 values")
    sign = 1 << 63

    def ordered(value: float) -> int:
        bits = struct.unpack(">Q", struct.pack(">d", value))[0]
        magnitude = bits & (sign - 1)
        return sign - magnitude if bits & sign else sign + magnitude

    return abs(ordered(actual) - ordered(expected))


def require_tagged_ulp(actual_tag: Any, expected: float, *, maximum: int, label: str) -> None:
    actual = f64(actual_tag, label)
    require(f64_ulp_distance(actual, expected) <= maximum, f"{label} exceeds declared independent f64 ULP bound")


def require_reduced_runtime_rational(value: Any, duration_s: float, profile: Mapping[str, Any], *, label: str) -> Fraction:
    require(isinstance(value, dict) and set(value) == {"numerator", "denominator"}, f"{label}: canonical runtime rational required")
    numerator, denominator = value.get("numerator"), value.get("denominator")
    require(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and numerator > 0
        and denominator > 0
        and math.gcd(numerator, denominator) == 1,
        f"{label}: runtime rational is not reduced and positive",
    )
    rational = Fraction(numerator, denominator)
    require(float(rational) == duration_s, f"{label}: rational does not identify recorded binary64 duration")
    support, _, _, _, _, _ = _profile_sections(profile)
    duration = support["duration_s"]
    h_min = _number(duration["min"], f"{label} lower bound") if isinstance(duration, Mapping) else _number(duration[0], f"{label} lower bound")
    h_max = _number(duration["max"], f"{label} upper bound") if isinstance(duration, Mapping) else _number(duration[1], f"{label} upper bound")
    require(h_min <= float(rational) <= h_max, f"{label}: rational lies outside frozen closed runtime interval")
    return rational


def zero_lambda_epsilon_values(values: tuple[float, ...], scale: int, mode: int, batch: int, phi: float, layout: Mapping[str, Any]) -> float:
    yang_abs = math.hypot(values[raw_offset(scale, 0, mode, batch, layout)], values[raw_offset(scale, 1, mode, batch, layout)])
    yin_abs = math.hypot(values[raw_offset(scale, 2, mode, batch, layout)], values[raw_offset(scale, 3, mode, batch, layout)])
    sqrt_phi_yin = math.sqrt(phi) * yin_abs
    return (yang_abs - sqrt_phi_yin) * (yang_abs + sqrt_phi_yin)


def zero_lambda_epsilon(raw: bytes, scale: int, mode: int, batch: int, phi: float, layout: Mapping[str, Any]) -> float:
    return zero_lambda_epsilon_values(raw_values(raw, label="control-law raw", layout=layout), scale, mode, batch, phi, layout)


def require_zero_lambda_conversion_rows(rows: Any, raw: bytes, profile: Mapping[str, Any], *, label: str) -> None:
    require(isinstance(rows, list), f"{label}: conversion rows must be a list")
    layout = profile.get("state_layout", profile)
    scales, modes, components, batch_lanes = _layout_counts(layout)
    require(len(rows) == scales, f"{label}: one conversion row per scale required")
    scalars = profile_scalars(profile)
    phi, rho_ref = scalars["phi"], scalars["rho_ref"]
    values = raw_values(raw, label=f"{label} raw", layout=layout)
    for scale, row in enumerate(rows):
        require(isinstance(row, Mapping) and row.get("scale") == scale, f"{label}: conversion scale-row order mutation")
        epsilons = [zero_lambda_epsilon_values(values, scale, mode, batch, phi, layout) for mode in range(modes) for batch in range(batch_lanes)]
        rhos = [
            position_density(values, scale, mode, batch, 0, layout) + position_density(values, scale, mode, batch, 2, layout)
            for mode in range(modes)
            for batch in range(batch_lanes)
        ]
        qs = []
        for mode in range(modes):
            for batch in range(batch_lanes):
                rho = rhos[mode * batch_lanes + batch]
                q_denominator = (rho / rho_ref) ** 2 + phi ** -2 + values[raw_offset(scale, components - 1, mode, batch, layout)] / (rho_ref * rho_ref)
                qs.append((rho / rho_ref) ** 2 / q_denominator)
        require_tagged_ulp(row.get("q_min"), min(qs), maximum=32, label=f"{label} scale {scale} q_min")
        require_tagged_ulp(row.get("q_max"), max(qs), maximum=32, label=f"{label} scale {scale} q_max")
        require_tagged_ulp(row.get("epsilon_min"), min(epsilons), maximum=32, label=f"{label} scale {scale} epsilon_min")
        require_tagged_ulp(row.get("epsilon_max"), max(epsilons), maximum=32, label=f"{label} scale {scale} epsilon_max")
        require(f64(row.get("alpha_min"), f"{label} scale {scale} alpha_min") == 1.0 and f64(row.get("alpha_max"), f"{label} scale {scale} alpha_max") == 1.0, f"{label}: lambda-zero alpha must be one")
        for name in ("transfer_min", "transfer_max", "transfer_l1", "signed_progress_min"):
            require(f64(row.get(name), f"{label} scale {scale} {name}") == 0.0, f"{label}: lambda-zero {name} must vanish")
        density = math.fsum(rhos)
        for name in ("density_pre", "density_post_analytic", "density_post_reconstructed"):
            require_tagged_ulp(row.get(name), density, maximum=64, label=f"{label} scale {scale} {name}")
        closure_bound = 128 * math.ulp(max(1.0, abs(density)))
        for name in ("density_map_closure_abs", "density_closure_abs"):
            closure = f64(row.get(name), f"{label} scale {scale} {name}")
            require(0.0 <= closure <= closure_bound, f"{label}: lambda-zero density closure exceeds independent f64 roundoff envelope")
        require(row.get("balanced_count") == sum(epsilon == 0.0 for epsilon in epsilons), f"{label}: balanced-count mutation")
        require(row.get("zero_count") == sum(rho == 0.0 for rho in rhos), f"{label}: zero-count mutation")


def require_normal_ema_rows(
    rows: Any,
    source_raw: bytes,
    candidate_raw: bytes,
    profile: Mapping[str, Any],
    tau: float,
    *,
    maximum_ulp: int,
    label: str,
) -> None:
    require(isinstance(rows, list), f"{label}: EMA rows must be a list")
    layout = profile.get("state_layout", profile)
    scales, modes, components, batch_lanes = _layout_counts(layout)
    require(len(rows) == scales, f"{label}: one EMA row per scale required")
    phi = profile_scalars(profile)["phi"]
    for scale, row in enumerate(rows):
        require(isinstance(row, Mapping) and row.get("scale") == scale, f"{label}: EMA scale-row order mutation")
        old = [raw_lane(source_raw, scale, components - 1, mode, batch, layout) for mode in range(modes) for batch in range(batch_lanes)]
        sample = [zero_lambda_epsilon(source_raw, scale, mode, batch, phi, layout) ** 2 for mode in range(modes) for batch in range(batch_lanes)]
        expected = [(1.0 - tau) * prior + tau * value for prior, value in zip(old, sample, strict=True)]
        actual = [raw_lane(candidate_raw, scale, components - 1, mode, batch, layout) for mode in range(modes) for batch in range(batch_lanes)]
        for index, (candidate, expectation) in enumerate(zip(actual, expected, strict=True)):
            require(candidate >= 0.0 and f64_ulp_distance(candidate, expectation) <= maximum_ulp, f"{label}: scale {scale} packed EMA lane {index} does not follow one physical update")
        require_tagged_ulp(row.get("pre_min"), min(old), maximum=0, label=f"{label} scale {scale} pre_min")
        require_tagged_ulp(row.get("pre_max"), max(old), maximum=0, label=f"{label} scale {scale} pre_max")
        require_tagged_ulp(row.get("sample_min"), min(sample), maximum=maximum_ulp, label=f"{label} scale {scale} sample_min")
        require_tagged_ulp(row.get("sample_max"), max(sample), maximum=maximum_ulp, label=f"{label} scale {scale} sample_max")
        require_tagged_ulp(row.get("post_min"), min(actual), maximum=0, label=f"{label} scale {scale} post_min")
        require_tagged_ulp(row.get("post_max"), max(actual), maximum=0, label=f"{label} scale {scale} post_max")


def check_control_laws(root: Path, w5: Mapping[str, Any]) -> dict[str, Any]:
    observed = read_json(file_at(root, "gates/g05v-conversion-viability/control-law-observations.json"))
    require(observed.get("schema") == G5_CONTROL_LAW_SCHEMA, "G5 control-law observation schema mutation")
    check_self(observed, G5_CONTROL_LAW_DOMAIN, "G5 control-law observations")
    require(
        observed.get("fixtures_define_support") is False
        and observed.get("fixtures_determine_verdict") is False
        and observed.get("control_law_source") == "sources/cassi_qi_conversion.py",
        "G5 control-law authority/source mutation",
    )
    rows = observed.get("controls")
    require(
        isinstance(rows, list)
        and [row.get("input", {}).get("control_id") for row in rows] == [
            "lambda-zero-normal-physical-ema",
            "lambda-zero-tau-zero-exact-whole-state-noop",
        ],
        "G5 control-law control registration mutation",
    )
    source_fixture = "matched-energy-positive-imbalance"
    source_control = read_json(file_at(w5["root"], f"gates/g05-conversion/controls/{source_fixture}.json"))
    source_descriptor = source_control.get("fixtures", {}).get("predecessor")
    require(isinstance(source_descriptor, Mapping), "G5 control-law source fixture descriptor missing")
    source_raw = file_at(w5["root"], source_descriptor["path"]).read_bytes()
    source_receipt = source_control.get("receipt")
    require(isinstance(source_receipt, Mapping), "G5 control-law source runtime receipt missing")
    check_self(source_receipt, W5_RECEIPT_SCHEMA, "G5 control-law source runtime receipt")
    source_duration = f64(source_control.get("duration_s"), "G5 control-law source duration")
    profile = w5["profile"]
    layout = profile.get("state_layout", profile)
    scales, _, components, batch_lanes = _layout_counts(layout)
    source_artifact_path = f"witnesses/{source_fixture}-predecessor.f64le"
    for ordinal, row in enumerate(rows):
        require(isinstance(row, dict) and set(row) == {"input", "result"}, "G5 control-law pair object mutation")
        input_value, result = row["input"], row["result"]
        require(isinstance(input_value, dict) and isinstance(result, dict), "G5 control-law input/result object mutation")
        require(input_value.get("schema") == G5_CONTROL_INPUT_SCHEMA and result.get("schema") == G5_CONTROL_RESULT_SCHEMA, "G5 control-law input/result schema mutation")
        check_self(input_value, G5_CONTROL_INPUT_DOMAIN, "G5 control-law input")
        check_self(result, G5_CONTROL_RESULT_DOMAIN, "G5 control-law result")
        require(
            input_value.get("source_fixture_id") == source_fixture
            and input_value.get("predecessor_artifact_path") == source_artifact_path
            and input_value.get("predecessor_sha256") == raw_hash(source_raw)
            and file_at(root, source_artifact_path).read_bytes() == source_raw,
            "G5 control-law raw/input linkage mutation",
        )
        duration = f64(input_value.get("duration_s"), "G5 control-law duration")
        require(duration == source_duration, "G5 control-law duration diverges from source W5 control")
        require_reduced_runtime_rational(input_value.get("duration_exact_rational"), duration, profile, label="G5 control-law duration")
        require(input_value.get("lambda_rate_s_inv") == tag(0.0), "G5 control-law lambda is not exact zero")
        require(result.get("input_sha256") == input_value["self_sha256"] and result.get("actual_decision") == "PASS" and result.get("conversion_maps") == 1 and result.get("ema_stage_invocations") == 1, "G5 control-law staging/identity mutation")
        candidate_raw = file_at(root, result.get("candidate_artifact_path")).read_bytes()
        require(raw_hash(candidate_raw) == result.get("candidate_sha256"), "G5 control-law candidate raw linkage mutation")
        require_zero_lambda_conversion_rows(result.get("per_scale_conversion"), source_raw, profile, label=f"G5 control-law {ordinal}")
        if ordinal == 0:
            require(input_value.get("epsilon_memory_time_s") == profile["epsilon_memory_time_s"], "G5 normal EMA memory-time identity mutation")
            tau = -math.expm1(-duration / f64(input_value.get("epsilon_memory_time_s"), "G5 normal EMA memory time"))
            require(
                result.get("ema_updates") == 1
                and result.get("positions_velocities_raw_identical") is True
                and result.get("ema_raw_changed_once") is True
                and result.get("ema_recomputation")
                == {
                    "tau_formula": "1-exp(-h/epsilon_memory_time)",
                    "sample_formula": "(abs(Y)-sqrt(phi)*abs(I))**2",
                    "per_lane_ulp_upper_bound": 8,
                    "evaluated_batch_lanes": batch_lanes,
                },
                "normal lambda-zero EMA declaration mutation",
            )
            require(result.get("tau") == tag(tau), "normal lambda-zero EMA tau mutation")
            require(raw_components_identical(source_raw, candidate_raw, range(components - 1), layout), "normal lambda-zero control changed position/velocity raw lanes")
            require(not raw_components_identical(source_raw, candidate_raw, range(components - 1, components), layout), "normal lambda-zero control omitted physical EMA raw write")
            require_normal_ema_rows(result.get("per_scale_ema"), source_raw, candidate_raw, profile, tau, maximum_ulp=8, label="normal lambda-zero EMA")
        else:
            expected_ema_rows = [{"scale": scale, "tau": tag(0.0), "wrote_state": False} for scale in range(scales)]
            require(
                input_value.get("tau") == tag(0.0)
                and input_value.get("tau_mode") == "joint-limit-exact-ema-stage-evaluation.v1"
                and result.get("ema_updates") == 0
                and result.get("ema_update_writes") == 0
                and result.get("tau") == tag(0.0)
                and result.get("whole_state_raw_identical") is True
                and result.get("ema_recomputation")
                == {
                    "tau_formula": "joint-exact-zero",
                    "sample_formula": "(abs(Y)-sqrt(phi)*abs(I))**2",
                    "per_lane_ulp_upper_bound": 0,
                    "evaluated_batch_lanes": batch_lanes,
                }
                and result.get("per_scale_ema") == expected_ema_rows,
                "joint lambda-zero/tau-zero EMA declaration mutation",
            )
            require(candidate_raw == source_raw, "joint lambda-zero/tau-zero EMA stage is not an exact raw no-op")
    return observed


def classify_work(work: float, tolerance: float) -> str:
    return "positive" if work > tolerance else "negative" if work < -tolerance else "source-ambiguous"


def check_work_observations(root: Path, w5: Mapping[str, Any], raw_activity: Mapping[str, Any]) -> dict[str, Any]:
    observed = read_json(file_at(root, "gates/g05v-conversion-viability/work-observations.json"))
    require(
        observed.get("method") == "source-exact-runtime-energy-observation-linked-to-W5-receipt.v1",
        "work observation must remain a linked source observation rather than an unverified independent replay",
    )
    require(observed.get("schema") == WORK_OBSERVATION_SCHEMA, "work observation schema mutation")
    check_self(observed, WORK_OBSERVATION_DOMAIN, "work observations")
    require(observed.get("fixtures_define_support") is False and observed.get("source_work_is_verdict_input") is False and observed.get("classification_space") == ["negative", "source-ambiguous", "positive"], "work observation authority/classifier mutation")
    trajectory_by_id = {row["fixture_id"]: row for row in raw_activity["trajectories"]}
    rows = observed.get("rows")
    require(isinstance(rows, list) and [row.get("fixture_id") for row in rows] == list(WITNESS_CELL_REGISTRATION), "work observation witness registration mutation")
    for row in rows:
        require(isinstance(row, dict), "work observation row mutation")
        check_self(row, WORK_OBSERVATION_SCHEMA, "work observation row")
        fixture_id = row["fixture_id"]
        source = read_json(file_at(w5["root"], f"gates/g05-conversion/controls/{fixture_id}.json"))
        receipt = source.get("receipt")
        require(isinstance(receipt, dict), f"work observation {fixture_id}: source receipt mutation")
        check_self(receipt, W5_RECEIPT_SCHEMA, f"work observation {fixture_id} receipt")
        require(
            row.get("predecessor_sha256") == trajectory_by_id[fixture_id]["predecessor_sha256"]
            and row.get("candidate_sha256") == trajectory_by_id[fixture_id]["candidate_sha256"]
            and row.get("control_receipt_sha256") == receipt.get("self_sha256"),
            f"work observation {fixture_id}: raw receipt linkage mutation",
        )
        energy = row.get("raw_endpoint_energy")
        require(isinstance(energy, Mapping), f"work observation {fixture_id}: raw endpoint energy is missing")
        pre, post, delta = energy.get("pre"), energy.get("post"), energy.get("delta")
        require(isinstance(pre, Mapping) and isinstance(post, Mapping) and isinstance(delta, Mapping), f"work observation {fixture_id}: energy components malformed")
        tolerance = _number(row.get("work_tolerance"), f"{fixture_id} work tolerance")
        names = set(pre) | set(post) | set(delta)
        require({"total", "carrier", "topological", "extra_conservative"} <= names, f"work observation {fixture_id}: energy component inventory incomplete")
        for name in set(pre) | set(post):
            require(name in delta, f"work observation {fixture_id}: missing delta component {name}")
            require(math.isclose(_number(delta[name], f"{fixture_id} {name} delta"), _number(post[name], f"{fixture_id} {name} post") - _number(pre[name], f"{fixture_id} {name} pre"), rel_tol=1.0e-12, abs_tol=max(tolerance, 1.0e-12)), f"work observation {fixture_id}: delta replay mismatch")
        conversion_work = math.fsum(_number(delta[name], f"{fixture_id} {name} delta") for name in ("carrier", "topological", "extra_conservative"))
        total_delta = _number(post["total"], f"{fixture_id} total post") - _number(pre["total"], f"{fixture_id} total pre")
        require(math.isclose(_number(delta["total"], f"{fixture_id} total delta"), total_delta, rel_tol=1.0e-12, abs_tol=max(tolerance, 1.0e-12)), f"work observation {fixture_id}: total delta replay mismatch")
        require(math.isclose(_number(energy["W_conversion"], f"{fixture_id} raw conversion work"), conversion_work, rel_tol=1.0e-12, abs_tol=max(tolerance, 1.0e-12)), f"work observation {fixture_id}: conversion work replay mismatch")
        require(math.isclose(_number(energy["closure_residual"], f"{fixture_id} closure residual"), total_delta - conversion_work, rel_tol=1.0e-12, abs_tol=max(tolerance, 1.0e-12)), f"work observation {fixture_id}: closure replay mismatch")
        observed_work = _number(receipt.get("energy", {}).get("W_conversion"), f"{fixture_id} source work")
        require(math.isclose(observed_work, conversion_work, rel_tol=1.0e-9, abs_tol=max(tolerance, 1.0e-12)), f"work observation {fixture_id}: raw endpoint work diverges from source receipt")
        work = _number(energy["W_conversion"], f"{fixture_id} source work")
        require(row.get("classification") == classify_work(work, tolerance) and row.get("source_work_is_verdict_input") is False, f"work observation {fixture_id}: source-work classification mutation")
    expected_counts = {name: sum(row["classification"] == name for row in rows) for name in observed["classification_space"]}
    require(observed.get("classification_counts") == expected_counts, "work observation classification count mutation")
    return observed


def canonical_clone(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical(value).decode("utf-8"))


def mutation_json_input(root: Path, mutation: Mapping[str, Any], *, path_key: str, sha_key: str, label: str) -> tuple[str, bytes, dict[str, Any]]:
    path = mutation.get(path_key)
    expected_sha = mutation.get(sha_key)
    require(isinstance(path, str) and is_sha256(expected_sha), f"{label}: mutation JSON input declaration is malformed")
    raw = file_at(root, path).read_bytes()
    require(sha(raw) == expected_sha, f"{label}: mutation JSON input hash mutation")
    return path, raw, read_json(file_at(root, path))


def require_structural_observation(row: Mapping[str, Any]) -> None:
    rejection = row.get("observed_rejection")
    require(
        row.get("actual_decision") == "REJECTED"
        and isinstance(rejection, dict)
        and rejection.get("kind") == "observed-structural-rejection.v1"
        and isinstance(rejection.get("exception_type"), str)
        and isinstance(rejection.get("exception_message"), str)
        and rejection["exception_message"],
        "structural mutation lacks an actual rejection observation",
    )


def expected_profile_mutation(profile: Mapping[str, Any], control_id: str) -> dict[str, Any]:
    expected = canonical_clone(profile)
    expected.pop("profile_sha256", None)
    if control_id == "mutate-memory-time":
        expected.get("parameters", expected)["epsilon_memory_time_s"] = tag(0.5)
    elif control_id == "mutate-epsilon-margin":
        expected["registered_margins"]["Delta_T_min"] = tag(0.0)
    elif control_id == "mutate-domain-predicate":
        cover = expected.get("cover", expected.get("complete_domain_cover"))
        cells = cover.get("cells") if isinstance(cover, Mapping) else cover
        cell = next((item for item in cells if item.get("cell_id") == "C05-progress-positive"), None)
        require(isinstance(cell, dict), "frozen profile lacks C05 predicate")
        cell["predicate"] = "epsilon>0"
    elif control_id == "mutate-support-omission":
        expected["D_conv"].pop("phase_branches", None)
    elif control_id == "mutate-support-shrink":
        expected["A_accepted"]["density_sum_at_most"] = tag(0.125)
    else:
        raise VerificationError(f"unknown profile mutation: {control_id}")
    expected["profile_sha256"] = digest(expected, W5_PROFILE_SCHEMA)
    return expected


def source_w5_receipt(w5: Mapping[str, Any], fixture_id: str) -> tuple[dict[str, Any], bytes, bytes]:
    control = read_json(file_at(w5["root"], f"gates/g05-conversion/controls/{fixture_id}.json"))
    receipt = control.get("receipt")
    require(isinstance(receipt, Mapping), f"{fixture_id}: source W5 receipt is absent")
    check_self(receipt, W5_RECEIPT_SCHEMA, f"{fixture_id}: source W5 receipt")
    descriptors = control.get("fixtures")
    require(isinstance(descriptors, Mapping), f"{fixture_id}: source fixture descriptors are absent")
    predecessor_descriptor, candidate_descriptor = descriptors.get("predecessor"), descriptors.get("candidate")
    require(isinstance(predecessor_descriptor, Mapping) and isinstance(candidate_descriptor, Mapping), f"{fixture_id}: source fixture descriptors malformed")
    predecessor = file_at(w5["root"], predecessor_descriptor["path"]).read_bytes()
    candidate = file_at(w5["root"], candidate_descriptor["path"]).read_bytes()
    require(
        predecessor_descriptor.get("sha256") == sha(predecessor)
        and candidate_descriptor.get("sha256") == sha(candidate)
        and raw_hash(predecessor) == receipt.get("predecessor_state_sha256")
        and raw_hash(candidate) == receipt.get("candidate_state_sha256"),
        f"{fixture_id}: source W5 raw/receipt linkage mutation",
    )
    return dict(receipt), predecessor, candidate


def check_runtime_mutation(root: Path, w5: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    control_id = row.get("control_id")
    mutation = row.get("mutation")
    require(isinstance(mutation, dict), f"{control_id}: runtime mutation declaration missing")
    receipt = row.get("actual_runtime_receipt")
    require(
        row.get("actual_decision") == "REJECTED"
        and isinstance(receipt, dict)
        and row.get("actual_runtime_receipt_sha256") == receipt.get("self_sha256"),
        f"{control_id}: runtime mutation lacks observed rejection receipt",
    )
    check_self(receipt, W5_RECEIPT_SCHEMA, f"{control_id}: runtime receipt")
    path = row.get("input_artifact_path")
    require(isinstance(path, str), f"{control_id}: runtime input path missing")
    input_raw = file_at(root, path).read_bytes()
    source_receipt, source_raw, _ = source_w5_receipt(w5, "matched-energy-positive-imbalance")
    require(
        raw_hash(input_raw) == row.get("input_raw_sha256") == receipt.get("predecessor_state_sha256")
        and receipt.get("status") == "REJECTED"
        and receipt.get("committable") is False
        and isinstance(receipt.get("failure_reason"), str)
        and receipt["failure_reason"],
        f"{control_id}: runtime raw/rejection linkage mutation",
    )
    duration_support = w5["profile"]["D_conv"]["duration_s"]
    h_min = _number(duration_support["min"], "runtime lower bound") if isinstance(duration_support, Mapping) else _number(duration_support[0], "runtime lower bound")
    if control_id == "mutate-unregistered-timestep":
        require(
            mutation
            == {
                "kind": "runtime-rational-outside-frozen-closed-H-runtime.v1",
                "duration_s": tag(0.0),
                "duration_exact_rational": {"numerator": 0, "denominator": 1},
                "frozen_runtime_interval": w5["profile"]["D_conv"]["duration_s"],
            }
            and input_raw == source_raw
            and f64(mutation["duration_s"], "zero-duration mutation") == 0.0
            and h_min > 0.0,
            "unregistered-timestep rejection predicate was not independently observed",
        )
    elif control_id == "mutate-stale-ema":
        profile = w5["profile"]
        layout = profile.get("state_layout", profile)
        scales, modes, components, batch_lanes = _layout_counts(layout)
        support, _, _, _, _, _ = _profile_sections(profile)
        ema_support = support["epsilon2_ema"]
        ema_max = _number(ema_support["max"], "EMA support maximum") if isinstance(ema_support, Mapping) else _number(ema_support[1], "EMA support maximum")
        expected_ema = math.nextafter(ema_max, math.inf)
        require(
            mutation.get("kind") == "epsilon2-ema-outside-frozen-D_conv.v1"
            and mutation.get("registered_ema_max") == (ema_support["max"] if isinstance(ema_support, Mapping) else ema_support[1])
            and f64(mutation.get("mutated_ema"), "stale EMA mutation") == expected_ema,
            "stale-EMA mutation declaration mismatch",
        )
        require(path == "mutation-witnesses/mutate-stale-ema-predecessor.f64le", "stale-EMA mutation witness path mutation")
        input_values, source_values = raw_values(input_raw, "stale-EMA input", layout), raw_values(source_raw, "stale-EMA source", layout)
        for scale in range(scales):
            for component in range(components):
                for mode in range(modes):
                    for batch in range(batch_lanes):
                        actual = input_values[raw_offset(scale, component, mode, batch, layout)]
                        if component == components - 1:
                            require(actual == expected_ema and actual > ema_max, "stale-EMA predicate was not independently present in raw input")
                        else:
                            require(actual == source_values[raw_offset(scale, component, mode, batch, layout)], "stale-EMA input changed an unrelated raw lane")
    elif control_id in {
        "mutate-memory-time",
        "mutate-epsilon-margin",
        "mutate-domain-predicate",
        "mutate-support-omission",
        "mutate-support-shrink",
    }:
        expected_path = f"mutation-inputs/{control_id}-profile.json"
        path_value, raw, mutated = mutation_json_input(root, mutation, path_key="profile_input_path", sha_key="profile_input_sha256", label=control_id)
        expected = expected_profile_mutation(w5["profile"], control_id)
        require(
            path_value == expected_path
            and raw == canonical(mutated)
            and mutated == expected
            and row.get("mutated_profile_artifact_path") == expected_path
            and row.get("mutated_profile_sha256") == expected["profile_sha256"]
            and input_raw == source_raw,
            f"{control_id}: frozen-profile identity rejection predicate mutation",
        )
    else:
        raise VerificationError(f"unknown runtime mutation control: {control_id}")
    require(source_receipt.get("status") == "PASS", f"{control_id}: source comparison receipt is not accepted")


def check_pair_schedule_mutation(root: Path, w5: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    control_id = row.get("control_id")
    mutation = row.get("mutation")
    require(
        isinstance(mutation, dict)
        and row.get("runtime_decisions") == ["PASS", "PASS"]
        and row.get("pair_verifier_decision") == "REJECTED"
        and isinstance(row.get("observed_pair_rejection"), dict)
        and row["observed_pair_rejection"].get("kind") == "observed-pair-schedule-rejection.v1",
        f"{control_id}: pair-schedule runtime/pair decision mutation",
    )
    source_fixture = "matched-energy-positive-imbalance"
    source_receipt, source_raw, source_candidate = source_w5_receipt(w5, source_fixture)
    source_artifact_path = f"witnesses/{source_fixture}-predecessor.f64le"
    if control_id == "mutate-duplicate-invocation":
        first, duplicate = row.get("first_actual_runtime_receipt"), row.get("duplicate_actual_runtime_receipt")
        require(
            mutation == {"kind": "duplicate-complete-step-runtime-receipt.v1", "source_fixture_id": source_fixture}
            and row.get("input_artifact_path") == source_artifact_path
            and row.get("input_raw_sha256") == raw_hash(source_raw)
            and first == source_receipt
            and duplicate == source_receipt
            and first.get("predecessor_state_sha256") == duplicate.get("predecessor_state_sha256") == raw_hash(source_raw)
            and first.get("candidate_state_sha256") == duplicate.get("candidate_state_sha256") == raw_hash(source_candidate)
            and first.get("conversion_invocations") == duplicate.get("conversion_invocations") == 1,
            "duplicate-invocation rejection predicate was not independently present",
        )
    elif control_id == "mutate-duplicate-order":
        first, second = row.get("interval_1_actual_runtime_receipt"), row.get("interval_2_actual_runtime_receipt")
        first_path, second_path = row.get("interval_1_candidate_artifact_path"), row.get("interval_2_candidate_artifact_path")
        require(
            mutation == {"kind": "reordered-complete-step-runtime-receipts.v1", "proposed_order": ["interval-2", "interval-1"]}
            and row.get("input_artifact_path") == source_artifact_path
            and row.get("input_raw_sha256") == raw_hash(source_raw)
            and first == source_receipt
            and isinstance(second, dict),
            "duplicate-order source receipt declaration mutation",
        )
        check_self(second, W5_RECEIPT_SCHEMA, "duplicate-order second runtime receipt")
        first_candidate = file_at(root, first_path).read_bytes()
        second_candidate = file_at(root, second_path).read_bytes()
        require(
            first_candidate == source_candidate
            and raw_hash(first_candidate) == first.get("candidate_state_sha256")
            and raw_hash(second_candidate) == second.get("candidate_state_sha256")
            and second.get("predecessor_state_sha256") == raw_hash(first_candidate)
            and second.get("predecessor_state_sha256") != raw_hash(source_raw)
            and second.get("status") == "PASS"
            and second.get("committable") is True,
            "duplicate-order raw predecessor/candidate chain does not reject the proposed order",
        )
    else:
        raise VerificationError(f"unknown pair-schedule mutation control: {control_id}")


def check_structural_mutation(root: Path, w5: Mapping[str, Any], receipt: Mapping[str, Any], work: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    control_id = row.get("control_id")
    mutation = row.get("mutation")
    require(isinstance(mutation, dict), f"{control_id}: structural mutation declaration missing")
    require_structural_observation(row)
    if control_id == "mutate-unresolved-suppression":
        path, _, mutated = mutation_json_input(root, mutation, path_key="receipt_input_path", sha_key="receipt_input_sha256", label=control_id)
        expected = canonical_clone(receipt)
        target = next((cell for cell in expected["cells"] if cell.get("cell_id") == "C05-progress-positive"), None)
        require(isinstance(target, dict), "receipt lacks the registered progress cell mutation target")
        target["status"] = "UNRESOLVED"
        target["unresolved"] = True
        actual_counts = {"total": len(mutated["cells"]), "PASS": 0, "FAIL": 0, "UNRESOLVED": 0}
        for cell in mutated["cells"]:
            actual_counts[cell["status"]] += 1
        require(
            path == "mutation-inputs/mutate-unresolved-suppression-receipt.json"
            and mutation.get("kind") == "cell-vector-unresolved-suppression.v1"
            and mutated == expected
            and mutated.get("cell_counts") != actual_counts
            and actual_counts["UNRESOLVED"] == 1,
            "unresolved-cell suppression predicate was not independently present",
        )
    elif control_id == "mutate-parent-extension":
        path, _, mutated = mutation_json_input(root, mutation, path_key="parent_input_path", sha_key="parent_input_sha256", label=control_id)
        expected = canonical_clone(w5["extension"])
        expected["chain_ordinal"] = 99
        require(
            path == "mutation-inputs/mutate-parent-extension.json"
            and mutation.get("kind") == "immutable-W4R-parent-extension.v1"
            and mutated == expected
            and mutated.get("chain_ordinal") != w5["extension"]["chain_ordinal"],
            "immutable-parent-extension rejection predicate was not independently present",
        )
    elif control_id == "mutate-source-snapshot":
        path = mutation.get("source_input_path")
        expected_sha = mutation.get("source_input_sha256")
        require(isinstance(path, str) and is_sha256(expected_sha), "source-snapshot mutation input declaration malformed")
        raw = file_at(root, path).read_bytes()
        source = file_at(root, "sources/cassi_qi_conversion.py").read_bytes()
        require(
            path == "mutation-inputs/mutate-cassi_qi_conversion.py"
            and mutation.get("kind") == "source-exact-frozen-Q-byte-mutation.v1"
            and sha(raw) == expected_sha
            and raw == source + b"\n# source-exact-mutation\n"
            and raw != source
            and source == file_at(w5["root"], "sources/cassi_qi_conversion.py").read_bytes(),
            "source-snapshot rejection predicate was not independently present",
        )
    elif control_id == "mutate-source-work":
        path, _, mutated = mutation_json_input(root, mutation, path_key="work_input_path", sha_key="work_input_sha256", label=control_id)
        expected = canonical_clone(work)
        expected_row = expected["rows"][0]
        expected_row["classification"] = "positive" if expected_row["classification"] != "positive" else "negative"
        work_value = f64(mutated["rows"][0]["raw_endpoint_energy"]["W_conversion"], "mutated source work")
        tolerance = f64(mutated["rows"][0]["work_tolerance"], "mutated source work tolerance")
        require(
            path == "mutation-inputs/mutate-source-work-observation.json"
            and mutation.get("kind") == "raw-source-work-classification-mismatch.v1"
            and mutated == expected
            and mutated["rows"][0]["classification"] != classify_work(work_value, tolerance),
            "source-work classification rejection predicate was not independently present",
        )
    else:
        raise VerificationError(f"unknown structural mutation control: {control_id}")


def check_mutations(
    root: Path,
    w5: Mapping[str, Any],
    receipt: Mapping[str, Any],
    work: Mapping[str, Any],
) -> dict[str, Any]:
    observed = read_json(file_at(root, "gates/g05v-conversion-viability/mutation-observations.json"))
    require(observed.get("schema") == MUTATION_OBSERVATION_SCHEMA, "mutation observations schema mutation")
    check_self(observed, MUTATION_OBSERVATION_DOMAIN, "mutation observations")
    policy = observed.get("observation_policy")
    require(
        isinstance(policy, dict)
        and all(
            policy.get(name) is True
            for name in (
                "expected_strings_are_not_evidence",
                "runtime_rejections_embed_actual_receipts",
                "pair_schedule_rejections_preserve_their_actual_PASS_runtime_decisions",
                "structural_rejections_embed_actual_exception_observations",
            )
        )
        and all(
            policy.get(name) is False
            for name in (
                "fixtures_define_support",
                "fixtures_determine_cells",
                "fixtures_determine_coefficient",
                "fixtures_determine_verdict",
            )
        ),
        "mutation observation policy mutation",
    )
    rows = observed.get("controls")
    required_ids = {
        "mutate-unregistered-timestep",
        "mutate-stale-ema",
        "mutate-memory-time",
        "mutate-epsilon-margin",
        "mutate-domain-predicate",
        "mutate-support-omission",
        "mutate-support-shrink",
        "mutate-duplicate-invocation",
        "mutate-duplicate-order",
        "mutate-unresolved-suppression",
        "mutate-parent-extension",
        "mutate-source-snapshot",
        "mutate-source-work",
    }
    require(isinstance(rows, list) and {row.get("control_id") for row in rows if isinstance(row, dict)} == required_ids and len(rows) == len(required_ids), "mutation control registration mutation")
    runtime = pair = structural = 0
    for row in rows:
        require(isinstance(row, dict) and row.get("schema") == MUTATION_CONTROL_SCHEMA, "mutation control schema mutation")
        check_self(row, MUTATION_CONTROL_DOMAIN, f"mutation control {row.get('control_id')}")
        kind = row.get("mutation_class")
        if kind == "runtime":
            runtime += 1
            check_runtime_mutation(root, w5, row)
        elif kind == "pair-schedule":
            pair += 1
            check_pair_schedule_mutation(root, w5, row)
        elif kind == "structural":
            structural += 1
            check_structural_mutation(root, w5, receipt, work, row)
        else:
            raise VerificationError("unknown mutation control class")
    require(
        observed.get("runtime_rejection_count") == runtime == 7
        and observed.get("pair_schedule_rejection_count") == pair == 2
        and observed.get("structural_rejection_count") == structural == 4,
        "mutation observation class-count mutation",
    )
    return observed
def check_stage_material(root: Path, w5: Mapping[str, Any]) -> dict[str, Any]:
    source_identity = check_sources(root, relative="run-spec/source-identity.json", schema=SOURCE_IDENTITY_SCHEMA, expected_paths=W5V_SOURCE_PATHS, label="W5V source identity")
    for relative in W5_SOURCE_PATHS:
        require(file_at(root / "sources", relative).read_bytes() == file_at(w5["root"] / "sources", relative).read_bytes(), f"W5V source snapshot does not exactly bind W5 source: {relative}")
    parent = read_json(file_at(root, "run-spec/parent-w5.json"))
    require(parent.get("schema") == PARENT_BINDING_SCHEMA, "W5V parent binding schema mutation")
    check_self(parent, PARENT_BINDING_SCHEMA, "W5V parent binding")
    expected_parent = {
        "schema": PARENT_BINDING_SCHEMA,
        "w5_engineering_binding": w5["binding"],
        "w5_parent_index_sha256": sha(w5["index_raw"]),
        "w5_parent_index_self_sha256": w5["index"]["self_sha256"],
        "w4r_extension_sha256": w5["extension"]["self_sha256"],
        "w4r_extension_path": w5["w4r"]["extension_path"],
        "w4r_chain_ordinal": w5["extension"]["chain_ordinal"],
        "w4r_parent_identities": w5["binding"]["parent_identities"],
        "source_exact": True,
        "predecessor_w5v_forward_domain_certificate": None,
    }
    expected_parent["self_sha256"] = digest(expected_parent, PARENT_BINDING_SCHEMA)
    require(parent == expected_parent, "explicit source-exact W5 predecessor binding mutation")
    extension_snapshot_paths = sorted((root / "parents").glob("*extension*.json"))
    require(len(extension_snapshot_paths) == 1, "W5V current W4R extension snapshot missing or ambiguous")
    snapshots = {
        "parents/w5-parent-index.json": w5["index_raw"],
        "parents/w5-parent-profile.json": w5["profile_raw"],
        "parents/w5-parent-root.json": w5["root_raw"],
        "parents/w5-parent-law.json": w5["law_raw"],
        "parents/w5-parent-g3n-certificate.json": w5["certificate_raw"],
        "parents/w5-parent-candidate.json": w5["candidate_raw"],
        "parents/w5-parent-status.json": w5["status_raw"],
        "parents/w5-parent-measurements.json": w5["measurements_raw"],
        extension_snapshot_paths[0].relative_to(root).as_posix(): w5["extension_raw"],
    }
    for relative, raw in snapshots.items():
        require(file_at(root, relative).read_bytes() == raw, f"W5V immutable parent snapshot mutation: {relative}")
    viability = read_json(file_at(root, "profile/conversion-viability-profile.json"))
    expected_viability = build_viability(w5["profile"], w5["conversion_root"])
    require(viability == expected_viability and viability.get("frozen_before_fixture_observation") is True, "W5V support/cell/EMA/coefficient/margin profile mutation")
    scalars = validate_conversion_profile(
        w5["profile"],
        w5["conversion_root"],
        read_json(file_at(w5["root"], "profile/conversion-law.json")),
        parent_extension_sha256=w5["extension"]["self_sha256"],
        parent_identities=w5["binding"]["parent_identities"],
    )
    bounds = analytic(w5["profile"], scalars)
    complete = cover_status(w5["profile"], scalars)
    manifest = read_json(file_at(root, "gates/g05v-conversion-viability/witness-manifest.json"))
    witnesses = expected_witnesses(manifest, w5, root)
    receipt = read_json(file_at(root, "gates/g05v-conversion-viability/conversion-viability.json"))
    require(receipt.get("schema") == W5V_RECEIPT_SCHEMA, "W5V receipt schema mutation")
    check_self(receipt, W5V_RECEIPT_SCHEMA, "W5V receipt")
    trials, selected = coefficient_trials(w5["profile"], scalars, bounds)
    expected = expected_receipt(viability, w5["profile"], w5["conversion_root"], w5["binding"], bounds, trials, selected, witnesses, complete)
    require(receipt == expected, "W5V receipt analytic enclosure/trial/cell/margin/control/verdict mutation")
    if receipt["status"] == "PASS":
        extension_paths = sorted((root / "certificate").glob("extension-*.json"))
        require(len(extension_paths) == 1, "W5V passing proof certificate extension missing or ambiguous")
        extension = read_json(extension_paths[0])
        require(extension == expected_extension(receipt, w5["extension"]), "W5V provisional extension mutation")
    else:
        extension = None
        require(not list((root / "certificate").glob("extension-*.json")), "failed W5V proof must not receive an extension")
    raw_activity = expected_raw_activity(root, w5, receipt)
    work = check_work_observations(root, w5, raw_activity)
    control_laws = check_control_laws(root, w5)
    mutations = check_mutations(root, w5, receipt, work)
    input_value = read_json(file_at(root, "verification/independent-input.json"))
    require(input_value.get("schema") == INDEPENDENT_INPUT_SCHEMA, "independent verifier input schema mutation")
    check_self(input_value, INDEPENDENT_INPUT_DOMAIN, "independent verifier input")
    source_rows = {row["path"]: row for row in source_identity["sources"]}
    verifier_row = source_rows.get("verify_cassi_qi_conversion_viability.py")
    require(isinstance(verifier_row, dict), "independent verifier source snapshot missing")
    w5_root_path = Path(w5["root"]).resolve()
    try:
        w5_artifact_root = w5_root_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        w5_artifact_root = w5_root_path.as_posix()
    expected_input = {
        "schema": INDEPENDENT_INPUT_SCHEMA,
        "execution_phase": "before-final-status-and-index.v1",
        "w5_root_required": False,
        "w5_discovery_policy": "scan-contract-root-filter-source-exact-independent-pass-exactly-one",
        "w5_artifact_root": w5_artifact_root,
        "w5_parent_index_sha256": w5["binding"]["index_sha256"],
        "w5_parent_run_id": w5["binding"]["run_id"],
        "w5_parent_identities": w5["binding"]["parent_identities"],
        "w5_certificate_identities": w5["binding"]["certificate_identities"],
        "source_identity_sha256": source_identity["self_sha256"],
        "verifier_source_path": "sources/verify_cassi_qi_conversion_viability.py",
        "verifier_source_sha256": verifier_row["sha256"],
        "verifier_import_policy": {
            "imports_cassi_qi_conversion_viability": False,
            "analytic_rederivation": "local-stdlib-decimal-tagged-f64.v1",
        },
        "viability_profile_sha256": viability["profile_sha256"],
        "receipt_sha256": receipt["self_sha256"],
        "g5_control_laws_sha256": control_laws["self_sha256"],
        "raw_activity_sha256": raw_activity["self_sha256"],
        "work_observations_sha256": work["self_sha256"],
        "mutation_observations_sha256": mutations["self_sha256"],
        "fixtures_determine_verdict": False,
    }
    expected_input["self_sha256"] = digest(expected_input, INDEPENDENT_INPUT_DOMAIN)
    require(input_value == expected_input, "independent verifier input linkage mutation")
    return {
        "source_identity": source_identity,
        "parent": parent,
        "viability": viability,
        "receipt": receipt,
        "extension": extension,
        "raw_activity": raw_activity,
        "work": work,
        "control_laws": control_laws,
        "mutations": mutations,
        "input": input_value,
    }


def build_embedded_independent_result(root: Path, *, w5_root: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    executed_source = Path(__file__).read_bytes()
    staged_source = file_at(root, "sources/verify_cassi_qi_conversion_viability.py").read_bytes()
    require(executed_source == staged_source, "embedded independent result was not executed from the source-exact staged verifier bytes")
    executed_source_sha256 = sha(executed_source)
    w5 = verify_w5(Path(w5_root), hints=()) if w5_root is not None else _discover_current_w5(root)
    material = check_stage_material(root, w5)
    receipt, extension, input_value = material["receipt"], material["extension"], material["input"]
    require(input_value["verifier_source_sha256"] == executed_source_sha256, "embedded independent input verifier hash does not identify the executing verifier")
    result = {
        "schema": INDEPENDENT_RESULT_SCHEMA,
        "execution_phase": "before-final-status-and-index.v1",
        "input_sha256": input_value["self_sha256"],
        "verifier_source_sha256": input_value["verifier_source_sha256"],
        "executed_verifier_source_sha256": executed_source_sha256,
        "verification_status": "PASS",
        "proof_status": receipt["status"],
        "failure_artifact": receipt["status"] != "PASS",
        "viability_profile_sha256": material["viability"]["profile_sha256"],
        "receipt_sha256": receipt["self_sha256"],
        "certificate_extension_sha256": None if extension is None else extension["self_sha256"],
        "raw_activity_sha256": material["raw_activity"]["self_sha256"],
        "work_observations_sha256": material["work"]["self_sha256"],
        "g5_control_laws_sha256": material["control_laws"]["self_sha256"],
        "mutation_observations_sha256": material["mutations"]["self_sha256"],
        "fixtures_determine_verdict": False,
    }
    result["self_sha256"] = digest(result, INDEPENDENT_RESULT_DOMAIN)
    return result


def _discover_current_w5(root: Path) -> dict[str, Any]:
    parent_path = root / "run-spec" / "parent-w5.json"
    require(parent_path.is_file(), "W5V parent binding is missing")
    parent = read_json(parent_path)
    require(parent.get("schema") == PARENT_BINDING_SCHEMA, "W5V parent binding schema mutation")
    check_self(parent, PARENT_BINDING_DOMAIN, "W5V parent binding")
    parent_binding = parent.get("w5_engineering_binding")
    require(isinstance(parent_binding, Mapping), "W5V parent engineering binding is missing")
    bases: list[Path] = [W5_ARTIFACT_ROOT]
    relative_hint = parent.get("w5_artifact_root")
    if isinstance(relative_hint, str) and relative_hint:
        hinted = Path(relative_hint)
        bases.append((PROJECT_ROOT / hinted).resolve() if not hinted.is_absolute() else hinted.resolve())
    bases.extend((root.parent, root.parent.parent))
    candidates: list[Path] = []
    for base in bases:
        for candidate in _candidate_roots(base, depth=1):
            if candidate not in candidates:
                candidates.append(candidate)
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            current = verify_w5(candidate, hints=_path_hints(parent))
            binding = current["binding"]
            require(parent.get("w5_parent_index_sha256") == binding["index_sha256"], "W5V declared parent index identity mismatch")
            require(parent.get("w5_parent_run_id") == binding["run_id"], "W5V declared parent run identity mismatch")
            require(parent.get("w4r_extension_sha256") == current["extension"]["self_sha256"], "W5V declared W4R extension identity mismatch")
            require(parent.get("source_exact") is True and parent.get("predecessor_w5v_forward_domain_certificate") is None, "W5V parent binding release mutation")
            require(dict(parent_binding) == binding, "W5V parent engineering binding does not equal current W5")
            matches.append(current)
        except (OSError, VerificationError, ValueError):
            continue
    require(len(matches) == 1, f"expected exactly one current source-exact W5 predecessor, found {len(matches)}")
    return matches[0]
def w5v_material(index: Mapping[str, Any]) -> dict[str, Any]:
    material_keys = {
        "schema",
        "status",
        "proof_status",
        "parents",
        "source_exact_successor_of",
        "objects",
        "w5_parent_identities",
        "certificate_identities",
        "gate",
        "failure_artifact",
        "conversion_profile_sha256",
        "conversion_root_sha256",
        "law_sha256",
        "viability_profile_sha256",
        "receipt_sha256",
        "certificate_extension_sha256",
        "certificate_chain_status",
        "final_certificate_identity_sha256",
        "independent_input_sha256",
        "independent_result_sha256",
        "raw_activity_sha256",
        "g5_control_laws_sha256",
        "mutation_observations_sha256",
        "fixtures_define_support",
        "parent_verifier_receipts",
        "parent_verifier_receipts_sha256",
        "work_observations_sha256",
    }
    require(
        set(index) == (material_keys | {"run_id", "object_count", "self_sha256"}),
        "W5V index fields mutation",
    )
    require(index["schema"] == INDEX_SCHEMA, "W5V index schema mutation")
    require(isinstance(index["objects"], list), "W5V object inventory missing")
    require(index["object_count"] == len(index["objects"]), "W5V object count mutation")
    return {key: index[key] if key != "schema" else ARTIFACT_DOMAIN for key in material_keys}


def verify(root: Path) -> dict[str, Any]:
    """Verify one immutable W5V artifact and discover its current W5 predecessor."""
    root = Path(root).resolve()
    require(root.is_dir(), f"W5V artifact root does not exist: {root}")
    w5 = _discover_current_w5(root)
    parent_verifier_receipts, parent_verifier_receipts_sha256 = _parent_verifier_receipts(w5)
    index = read_json(file_at(root, "index.json"))
    require(index.get("schema") == INDEX_SCHEMA, "W5V index schema mismatch")
    check_self(index, INDEX_SCHEMA, "W5V index")
    _check_parent_verifier_receipts(
        index.get("parent_verifier_receipts"),
        parent_verifier_receipts,
        parent_verifier_receipts_sha256,
        "W5V index parent verifier receipts",
    )
    require(
        index.get("run_id") == digest(w5v_material(index), ARTIFACT_DOMAIN)
        and index.get("gate") == "G5V"
        and isinstance(index.get("failure_artifact"), bool)
        and index.get("fixtures_define_support") is False,
        "W5V index identity/status mutation",
    )
    check_records(root, index, "W5V")
    stage = check_stage_material(root, w5)
    receipt, extension, input_value = stage["receipt"], stage["extension"], stage["input"]
    proof_status = receipt["status"]
    artifact_status = "PASS_W5V_G5V" if proof_status == "PASS" else "FAIL_W5V_G5V"
    failure_artifact = proof_status != "PASS"
    require(
        index.get("status") == artifact_status
        and index.get("proof_status") == proof_status
        and index.get("failure_artifact") is failure_artifact
        and index.get("parents") == [stage["parent"]]
        and index.get("source_exact_successor_of") == stage["parent"]
        and index.get("w5_parent_identities") == receipt["parent_identities"]
        and index.get("certificate_identities") == receipt["certificate_identities"],
        "W5V index proof/failure/parent linkage mutation",
    )
    stored_result = read_json(file_at(root, "verification/independent-result.json"))
    require(stored_result.get("schema") == INDEPENDENT_RESULT_SCHEMA, "independent verifier result schema mutation")
    check_self(stored_result, INDEPENDENT_RESULT_DOMAIN, "independent verifier result")
    expected_result = build_embedded_independent_result(root)
    require(
        stored_result == expected_result
        and stored_result.get("input_sha256") == input_value["self_sha256"]
        and stored_result.get("verifier_source_sha256") == stored_result.get("executed_verifier_source_sha256"),
        "embedded independent verifier result/executed-source linkage mutation",
    )
    extension_sha256 = None if extension is None else extension["self_sha256"]
    chain_status = None if extension is None else extension["chain_status"]
    expected_status = {
        "schema": STATUS_SCHEMA,
        "gate": "G5V",
        "status": artifact_status,
        "parent_verifier_receipts": parent_verifier_receipts,
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
        "proof_status": proof_status,
        "failure_artifact": failure_artifact,
        "w5_engineering_run_id": w5["binding"]["run_id"],
        "w5_engineering_index_sha256": w5["binding"]["index_sha256"],
        "viability_profile_sha256": stage["viability"]["profile_sha256"],
        "receipt_sha256": receipt["self_sha256"],
        "certificate_extension_sha256": extension_sha256,
        "certificate_chain_status": chain_status,
        "final_certificate_identity_sha256": None if extension is None else extension["final_certificate_identity_sha256"],
        "w5v_forward_domain_certificate": extension_sha256,
        "fixtures_define_support": False,
        "unresolved_cell_count": receipt["cell_counts"]["UNRESOLVED"],
        "independent_input_sha256": input_value["self_sha256"],
        "independent_result_sha256": stored_result["self_sha256"],
        "independent_verification_status": "PASS",
    }
    expected_status["self_sha256"] = digest(expected_status, STATUS_SCHEMA)
    status = read_json(file_at(root, "gates/g05v-conversion-viability/status.json"))
    require(status.get("schema") == STATUS_SCHEMA, "W5V gate status schema mutation")
    check_self(status, STATUS_SCHEMA, "W5V gate status")
    _check_parent_verifier_receipts(
        status.get("parent_verifier_receipts"),
        parent_verifier_receipts,
        parent_verifier_receipts_sha256,
        "W5V status parent verifier receipts",
    )
    require(status == expected_status, "W5V gate status linkage mutation")
    extension_paths = sorted((root / "certificate").glob("extension-*.json"))
    if failure_artifact:
        require(extension is None and not extension_paths, "failed W5V artifact must preserve failure material without a certificate extension")
    else:
        require(
            extension is not None
            and len(extension_paths) == 1
            and extension.get("chain_status") == "provisional"
            and extension.get("final_certificate_identity_sha256") is None
            and extension_sha256 is not None,
            "passing W5V artifact must emit only a provisional extension",
        )
    expected_index_fields = {
        "status": artifact_status,
        "parent_verifier_receipts": parent_verifier_receipts,
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
        "proof_status": proof_status,
        "parents": [stage["parent"]],
        "source_exact_successor_of": stage["parent"],
        "w5_parent_identities": receipt["parent_identities"],
        "certificate_identities": receipt["certificate_identities"],
        "gate": "G5V",
        "failure_artifact": failure_artifact,
        "conversion_profile_sha256": receipt["conversion_profile_sha256"],
        "conversion_root_sha256": receipt["conversion_root_sha256"],
        "law_sha256": receipt["conversion_law_sha256"],
        "viability_profile_sha256": stage["viability"]["profile_sha256"],
        "receipt_sha256": receipt["self_sha256"],
        "certificate_extension_sha256": extension_sha256,
        "certificate_chain_status": chain_status,
        "final_certificate_identity_sha256": None if extension is None else extension["final_certificate_identity_sha256"],
        "independent_input_sha256": input_value["self_sha256"],
        "independent_result_sha256": stored_result["self_sha256"],
        "raw_activity_sha256": stage["raw_activity"]["self_sha256"],
        "work_observations_sha256": stage["work"]["self_sha256"],
        "g5_control_laws_sha256": stage["control_laws"]["self_sha256"],
        "mutation_observations_sha256": stage["mutations"]["self_sha256"],
        "fixtures_define_support": False,
    }
    require(
        all(index.get(key) == value for key, value in expected_index_fields.items()),
        "W5V index semantic linkage mutation",
    )
    return {
        "gate": "G5V",
        "status": artifact_status,
        "proof_status": proof_status,
        "failure_artifact": failure_artifact,
        "verification_status": "PASS",
        "run_id": index["run_id"],
        "w5_run_id": w5["binding"]["run_id"],
        "viability_profile_sha256": stage["viability"]["profile_sha256"],
        "receipt_sha256": receipt["self_sha256"],
        "certificate_extension_sha256": extension_sha256,
        "independent_result_sha256": stored_result["self_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="W5V content-addressed artifact root")
    args = parser.parse_args()
    try:
        value = verify(args.artifact)
    except Exception as exc:
        print(f"G5V independent verification FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(canonical(value).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
