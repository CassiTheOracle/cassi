"""W3N/G3N numerical certificate and immutable online guard.

The certificate is derived from the validated, current W2 periodic-FFT2 material
and the validated W3 transport profile.  The online path only checks sealed
scalar/layout limits; it never derives, widens, clips, or mutates state.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import math
import struct
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from cassi_qi_profile import canonical_hash, canonical_json_bytes, finite_float
from cassi_qi_transport import (
    W2_PARENT_RECORD,
    W3_G3_STAGE_SCHEDULE,
    W3_STAGE_SCHEDULE_SCHEMA,
    validate_w3_transport_profile,
)


NUMERICAL_CERTIFICATE_SCHEMA = "cassi.qi-flow-numerical-certificate.v1"
CERTIFICATE_EXTENSION_SCHEMA = "cassi.qi-flow-certificate-extension.v1"
CERTIFICATE_REGISTRY_EXTENSION_SCHEMA = "cassi.qi-flow-schema-registry-extension.v1"
NUMERICAL_GUARD_SCHEMA = "cassi.qi-flow-numerical-guard.v1"
NUMERICAL_GUARD_RECEIPT_SCHEMA = "cassi.qi-flow-numerical-guard-receipt.v1"
NUMERICAL_DERIVATION_SCHEMA = "cassi.qi-flow-w3n-offline-derivation.v1"
NUMERICAL_SECTION_SCHEMA = "cassi.qi-flow-w3n-intrinsic-section.v1"
NUMERICAL_RAW_STATE_DOMAIN = "cassi.qi-flow-w3n-raw-state.v1"
NUMERICAL_CERTIFICATE_DOMAIN = "cassi.qi-flow-w3n-certificate.v1"
NUMERICAL_EXTENSION_DOMAIN = "cassi.qi-flow-w3n-extension.v1"
NUMERICAL_GUARD_DOMAIN = "cassi.qi-flow-w3n-guard.v1"
NUMERICAL_EXTENSION_REGISTRY_DOMAIN = "cassi.qi-flow-w3n-registry-extension.v1"
W3_ARTIFACT_IDENTITY_SCHEMA = "cassi.qi-flow-w3-artifact-identity.v1"
PRECISION_DIGITS = 80
ROUNDING_MODE = "decimal-80-directed-nextafter-f64.v1"
REQUIRED_W3N_SECTIONS = ("intrinsic-w3-numerics",)

G3N_EXECUTED_CONTROL_IDS = (
    "duplicate-root", "duplicate-nested", "nan", "infinity", "decimal-number",
    "malformed-tag", "negative-zero", "trailing-data", "coefficient",
    "lower-endpoint", "upper-endpoint", "precision", "rounding", "dtype",
    "backend", "source-budget", "extension_parent", "section_self_hash",
    "inventory_omit", "inventory_duplicate", "inventory_reorder", "extension_ordinal",
    "rounding_budget", "registry_parent", "registry_entry_schema_owner",
    "registry_duplicate", "registry_omit", "source_path", "source_digest",
    "source_count", "live_source_substitution", "w3_artifact_identity",
    "w3_artifact_source_digest", "run_parent_run_id", "parent_index_hash",
    "parent_list_order_duplication", "stale_different_w3_parent", "guard_decision",
    "guard_reason", "guard_mutation_permitted", "guard_dtype", "guard_backend",
    "guard_source_byte_count", "guard_source_byte_budget", "guard_raw_hash",
    "guard_raw_byte_count", "guard_threshold", "guard_maximum",
    "guard_contract_hash", "guard_receipt_self_hash", "raw_fixture_outer_index",
    "raw_fixture_receipt_candidate_status_index",
)


class NumericalCertificateError(ValueError):
    """Raised when current W2/W3 material cannot produce a certificate."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NumericalCertificateError(message)


def _f64(value: float) -> str:
    value = float(value)
    _require(math.isfinite(value), "certificate scalar must be finite")
    _require(not (value == 0.0 and math.copysign(1.0, value) < 0.0), "negative zero is forbidden")
    return "f64:" + struct.pack(">d", value).hex()


def _decode(value: Any, *, name: str) -> float:
    try:
        result = finite_float(value, name=name)
    except Exception as exc:
        raise NumericalCertificateError(f"invalid {name}") from exc
    _require(math.isfinite(result), f"{name} is not finite")
    _require(not (result == 0.0 and math.copysign(1.0, result) < 0.0), f"{name} is negative zero")
    return float(result)


def _decimal(value: Any, *, name: str) -> Decimal:
    return Decimal.from_float(_decode(value, name=name))


def _tag_decimal(value: Decimal) -> str:
    return _f64(float(value))


def _outward(lower: Decimal, upper: Decimal) -> dict[str, str]:
    _require(lower <= upper, "interval bounds are reversed")
    return {"lower": _f64(math.nextafter(float(lower), -math.inf)), "upper": _f64(math.nextafter(float(upper), math.inf))}


def _nonnegative_interval(upper: Decimal) -> dict[str, str]:
    _require(upper >= 0, "nonnegative interval has a negative upper bound")
    return {"lower": _f64(0.0), "upper": _f64(math.nextafter(float(upper), math.inf))}


def _raw_hash(raw: bytes, *, shape: Sequence[int]) -> str:
    domain = NUMERICAL_RAW_STATE_DOMAIN.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    dtype = b"float64"
    digest.update(len(dtype).to_bytes(8, "big"))
    digest.update(dtype)
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        _require(isinstance(dimension, int) and dimension >= 0, "raw layout dimension must be nonnegative")
        digest.update(struct.pack(">Q", dimension))
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


_EXTENSION_CONTROLLED_FIELDS = frozenset({
    "schema", "certificate_chain_id", "chain_ordinal", "parent_certificate_sha256",
    "parent_section_inventory", "owning_package", "gate", "added_section",
    "complete_section_inventory", "chain_status",
    "final_certificate_identity_sha256", "self_sha256",
})


def _self_hash(value: Mapping[str, Any], domain: str) -> str:
    return canonical_hash({str(key): _plain(item) for key, item in value.items() if key != "self_sha256"}, domain)


def _require_text(value: Any, *, name: str) -> str:
    _require(isinstance(value, str) and value, f"{name} is missing")
    return value


def _validated_chain_parent(
    parent: Mapping[str, Any],
    *,
    parent_schema: str,
    parent_domain: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    _require(isinstance(parent, Mapping), "certificate-extension parent is not an object")
    record = _plain(parent)
    _require(record.get("schema") == parent_schema, "certificate-extension parent schema mismatch")
    stored_self = _require_text(record.get("self_sha256"), name="certificate-extension parent self hash")
    _require(stored_self == _self_hash(record, parent_domain), "certificate-extension parent self hash mismatch")
    _require_text(record.get("certificate_chain_id"), name="certificate-extension parent chain identifier")
    ordinal = record.get("chain_ordinal")
    _require(isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal >= 0, "certificate-extension parent ordinal is invalid")
    inventory = record.get("complete_section_inventory")
    _require(isinstance(inventory, list), "certificate-extension parent inventory is missing")
    inventory_rows = [_plain(row) for row in inventory]
    _require(all(isinstance(row, dict) for row in inventory_rows), "certificate-extension parent inventory has a non-object section")
    _require(len(inventory_rows) == ordinal, "certificate-extension parent inventory is incomplete")
    _require([row.get("ordinal") for row in inventory_rows] == list(range(1, ordinal + 1)), "certificate-extension parent inventory is reordered")
    return record, inventory_rows, ordinal


def _sealed_extension_section(
    section_body: Mapping[str, Any],
    *,
    section_schema: str,
    section_domain: str,
    ordinal: int,
    owning_package: str,
    gate: str,
    sealed: bool = False,
) -> dict[str, Any]:
    _require(isinstance(section_body, Mapping), "certificate-extension section is not an object")
    section = _plain(section_body)
    stored_self = section.pop("self_sha256", None)
    _require((stored_self is not None) if sealed else (stored_self is None), "certificate-extension section seal state is invalid")
    _require(section.get("schema") == section_schema, "certificate-extension section schema mismatch")
    _require_text(section.get("section_id"), name="certificate-extension section identifier")
    _require(section.get("owning_package") == owning_package, "certificate-extension section owner mismatch")
    _require(section.get("gate") == gate, "certificate-extension section gate mismatch")
    _require(section.get("ordinal", ordinal) == ordinal, "certificate-extension section ordinal mismatch")
    section["ordinal"] = ordinal
    section["self_sha256"] = canonical_hash(section, section_domain)
    if sealed:
        _require(stored_self == section["self_sha256"], "certificate-extension section self hash mismatch")
    return section


def build_certificate_extension(
    *,
    parent: Mapping[str, Any],
    parent_schema: str,
    parent_domain: str,
    extension_schema: str,
    extension_domain: str,
    section_body: Mapping[str, Any],
    section_schema: str,
    section_domain: str,
    owning_package: str,
    gate: str,
    chain_status: str,
    final_certificate_identity: bool,
    extra_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Append and seal one immutable certificate section from a sealed parent."""
    parent_record, parent_inventory, parent_ordinal = _validated_chain_parent(
        parent,
        parent_schema=parent_schema,
        parent_domain=parent_domain,
    )
    _require_text(extension_schema, name="certificate-extension schema")
    _require_text(extension_domain, name="certificate-extension domain")
    _require_text(owning_package, name="certificate-extension owner")
    _require_text(gate, name="certificate-extension gate")
    _require_text(chain_status, name="certificate-extension chain status")
    _require(isinstance(final_certificate_identity, bool), "certificate-extension final-identity mode is invalid")
    if extra_fields is None:
        extras: dict[str, Any] = {}
    else:
        _require(isinstance(extra_fields, Mapping), "certificate-extension extra fields are not an object")
        extras = _plain(extra_fields)
    _require(not (_EXTENSION_CONTROLLED_FIELDS & set(extras)), "certificate-extension extra fields overwrite a structural field")
    ordinal = parent_ordinal + 1
    section = _sealed_extension_section(
        section_body,
        section_schema=section_schema,
        section_domain=section_domain,
        ordinal=ordinal,
        owning_package=owning_package,
        gate=gate,
    )
    extension: dict[str, Any] = {
        "schema": extension_schema,
        "certificate_chain_id": parent_record["certificate_chain_id"],
        "chain_ordinal": ordinal,
        "parent_certificate_sha256": parent_record["self_sha256"],
        "parent_section_inventory": parent_inventory,
        "owning_package": owning_package,
        "gate": gate,
        **extras,
        "added_section": section,
        "complete_section_inventory": [*parent_inventory, section],
        "chain_status": chain_status,
    }
    extension["final_certificate_identity_sha256"] = (
        canonical_hash(extension, extension_domain) if final_certificate_identity else None
    )
    extension["self_sha256"] = canonical_hash(extension, extension_domain)
    return validate_certificate_extension(
        extension,
        parent=parent_record,
        parent_schema=parent_schema,
        parent_domain=parent_domain,
        extension_schema=extension_schema,
        extension_domain=extension_domain,
        section_schema=section_schema,
        section_domain=section_domain,
        final_certificate_identity=final_certificate_identity,
    )


def validate_certificate_extension(
    extension: Mapping[str, Any],
    *,
    parent: Mapping[str, Any],
    parent_schema: str,
    parent_domain: str,
    extension_schema: str,
    extension_domain: str,
    section_schema: str,
    section_domain: str,
    final_certificate_identity: bool,
) -> dict[str, Any]:
    """Validate chain ancestry, contiguous inventory, and both extension seals."""
    _require(isinstance(extension, Mapping), "certificate extension is not an object")
    parent_record, parent_inventory, parent_ordinal = _validated_chain_parent(
        parent,
        parent_schema=parent_schema,
        parent_domain=parent_domain,
    )
    record = _plain(extension)
    _require(record.get("schema") == extension_schema, "certificate extension schema mismatch")
    _require(record.get("certificate_chain_id") == parent_record["certificate_chain_id"], "certificate extension chain identifier mismatch")
    ordinal = parent_ordinal + 1
    _require(record.get("chain_ordinal") == ordinal, "certificate extension ordinal mismatch")
    _require(record.get("parent_certificate_sha256") == parent_record["self_sha256"], "certificate extension parent hash mismatch")
    _require(record.get("parent_section_inventory") == parent_inventory, "certificate extension parent inventory mismatch")
    owning_package = _require_text(record.get("owning_package"), name="certificate extension owner")
    gate = _require_text(record.get("gate"), name="certificate extension gate")
    section = record.get("added_section")
    _require(isinstance(section, Mapping), "certificate extension added section is missing")
    sealed_section = _sealed_extension_section(
        section,
        section_schema=section_schema,
        section_domain=section_domain,
        ordinal=ordinal,
        owning_package=owning_package,
        gate=gate,
        sealed=True,
    )
    _require(section == sealed_section, "certificate extension added-section seal mismatch")
    inventory = record.get("complete_section_inventory")
    _require(isinstance(inventory, list), "certificate extension inventory is missing")
    _require(inventory == [*parent_inventory, sealed_section], "certificate extension inventory mismatch")
    _require_text(record.get("chain_status"), name="certificate extension chain status")
    _require(isinstance(final_certificate_identity, bool), "certificate-extension final-identity mode is invalid")
    _require(record.get("final_certificate_identity_sha256") == (
        canonical_hash(
            {str(key): _plain(value) for key, value in record.items() if key not in {"self_sha256", "final_certificate_identity_sha256"}},
            extension_domain,
        ) if final_certificate_identity else None
    ), "certificate extension final identity mismatch")
    _require(record.get("self_sha256") == _self_hash(record, extension_domain), "certificate extension self hash mismatch")
    return record


def raw_state_bytes_from_field(field: Any) -> bytes:
    """Return canonical little-endian bytes without changing the tensor."""
    try:
        import torch
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise NumericalCertificateError("torch is required for the W3N state guard") from exc
    if not isinstance(field, torch.Tensor) or field.device.type != "cpu" or field.dtype != torch.float64:
        raise NumericalCertificateError("W3N guard accepts only CPU float64 tensors")
    if field.ndim != 3 or any(int(size) <= 0 for size in field.shape):
        raise NumericalCertificateError("W3N field must be a non-empty rank-three packed layout")
    return field.detach().contiguous().numpy().astype("<f8", copy=False).tobytes(order="C")


def _scale_rows(geometry: Any) -> list[dict[str, Any]]:
    payload = _plain(getattr(geometry, "payload", {}))
    contract = payload.get("geometry_contract")
    _require(isinstance(contract, Mapping), "W2 geometry contract is missing")
    sheets = contract.get("per_scale_sheets")
    _require(isinstance(sheets, list) and sheets, "W2 has no per-scale sheets")
    rows: list[dict[str, Any]] = []
    for scale, sheet in enumerate(sheets):
        _require(isinstance(sheet, Mapping), f"W2 scale {scale} sheet is not an object")
        rectangle = sheet.get("active_rectangle")
        shape = rectangle.get("shape_yx") if isinstance(rectangle, Mapping) else None
        _require(isinstance(shape, list) and len(shape) == 2 and all(isinstance(n, int) and n > 0 for n in shape), f"W2 scale {scale} shape is invalid")
        _require(sheet.get("scale") == scale, "W2 scale order is not canonical")
        spacing = sheet.get("spacing_m")
        extent = sheet.get("extent_m")
        _require(isinstance(spacing, list) and len(spacing) == 2, f"W2 scale {scale} spacing is missing")
        _require(isinstance(extent, list) and len(extent) == 2, f"W2 scale {scale} extent is missing")
        dy = _decode(spacing[0], name=f"W2 scale {scale} dy")
        dx = _decode(spacing[1], name=f"W2 scale {scale} dx")
        ly = _decode(extent[0], name=f"W2 scale {scale} L_y")
        lx = _decode(extent[1], name=f"W2 scale {scale} L_x")
        _require(dy > 0 and dx > 0 and ly > 0 and lx > 0, f"W2 scale {scale} lengths must be positive")
        frequencies_y = sheet.get("signed_frequency_y")
        frequencies_x = sheet.get("signed_frequency_x")
        _require(isinstance(frequencies_y, list) and isinstance(frequencies_x, list), f"W2 scale {scale} signed bins are missing")
        _require(len(frequencies_y) == shape[0] and len(frequencies_x) == shape[1], f"W2 scale {scale} signed bins do not cover the active sheet")
        _require(all(isinstance(n, int) and not isinstance(n, bool) for n in frequencies_y + frequencies_x), f"W2 scale {scale} has invalid signed bins")
        active_sites = sheet.get("active_site_count")
        _require(active_sites == shape[0] * shape[1], f"W2 scale {scale} active site count mismatch")
        oversampling = sheet.get("oversampling")
        _require(isinstance(oversampling, Mapping), f"W2 scale {scale} oversampling is missing")
        factors = oversampling.get("factors_yx")
        fine_shape = oversampling.get("shape_yx")
        _require(isinstance(factors, list) and len(factors) == 2 and all(isinstance(n, int) and n >= 1 for n in factors), f"W2 scale {scale} oversampling factors are invalid")
        _require(isinstance(fine_shape, list) and len(fine_shape) == 2 and fine_shape == [shape[0] * factors[0], shape[1] * factors[1]], f"W2 scale {scale} fine shape mismatch")
        area = _decode(sheet.get("cell_area_m2"), name=f"W2 scale {scale} cell area")
        _require(area > 0, f"W2 scale {scale} cell area must be positive")
        rows.append({
            "scale": scale,
            "shape_yx": list(shape),
            "active_site_count": active_sites,
            "spacing_m": {"dy": _f64(dy), "dx": _f64(dx)},
            "extent_m": {"L_y": _f64(ly), "L_x": _f64(lx)},
            "cell_area_m2": _f64(area),
            "signed_frequency_y": list(frequencies_y),
            "signed_frequency_x": list(frequencies_x),
            "oversampling": _plain(oversampling),
        })
    return rows


def _semantic_and_parameters(transport: Any) -> tuple[Mapping[str, Any], Any]:
    semantic = _plain(getattr(transport, "semantic_payload", {}))
    if not isinstance(semantic, Mapping) or not semantic:
        payload = _plain(getattr(transport, "payload", {}))
        semantic = payload.get("semantic", {}) if isinstance(payload, Mapping) else {}
    parameters = getattr(transport, "pinned_parameters", None)
    _require(isinstance(semantic, Mapping) and parameters is not None, "validated W3 semantic material is missing")
    return semantic, parameters


def _param(semantic: Mapping[str, Any], parameters: Any, name: str, *aliases: str) -> Any:
    dynamics = semantic.get("dynamics", {})
    for key in (name, *aliases):
        if isinstance(dynamics, Mapping) and key in dynamics:
            return dynamics[key]
    attr = {
        "h_s": "h", "c_D_m_per_s": "c_D_m_per_s", "omega_D_rad_per_s": "omega_rad_per_s",
        "gamma_D_per_s": "gamma_per_s", "kappa_D": "kappa", "candidate_amplitude_cap": "amplitude_cap",
        "rho_floor": "rho_floor", "candidate_numerical_tolerance": "candidate_numerical_tolerance",
        "source_budget_bytes": "max_source_budget", "phi": "phi",
    }.get(name, name)
    value = getattr(parameters, attr, None)
    _require(value is not None, f"W3 parameter {name} is missing")
    return value


def _oscillator_bound(omega: Decimal, gamma: Decimal, duration: Decimal) -> tuple[str, Decimal]:
    """Frobenius bound of the exact normalized damped-oscillator matrix."""
    if duration == 0:
        return "identity", Decimal(1)
    alpha = gamma / Decimal(2)
    if omega > alpha:
        branch = "underdamped"
        frequency = (omega * omega - alpha * alpha).sqrt()
        sine, cosine = _decimal_sin_cos(frequency * duration)
        s_over = sine / frequency
        decay = (-alpha * duration).exp()
        a11 = decay * (cosine + alpha * s_over)
        a12 = decay * s_over
        a21 = decay * (-(omega * omega) * s_over)
        a22 = decay * (cosine - alpha * s_over)
    elif omega == alpha:
        branch = "critical"
        decay = (-alpha * duration).exp()
        a11 = decay * (Decimal(1) + alpha * duration)
        a12 = decay * duration
        a21 = decay * (-(omega * omega) * duration)
        a22 = decay * (Decimal(1) - alpha * duration)
    else:
        branch = "overdamped"
        frequency = (alpha * alpha - omega * omega).sqrt()
        sine, cosine = _decimal_sinh_cosh(frequency * duration)
        s_over = sine / frequency
        decay = (-alpha * duration).exp()
        a11 = decay * (cosine + alpha * s_over)
        a12 = decay * s_over
        a21 = decay * (-(omega * omega) * s_over)
        a22 = decay * (cosine - alpha * s_over)
    if omega > 0:
        entries = (a11, omega * a12, a21 / omega, a22)
    else:
        entries = (a11, a12, a21, a22)
    return branch, sum(value * value for value in entries).sqrt()


def _decimal_pi() -> Decimal:
    """Compute pi from a convergent exact rational Machin series."""
    from decimal import getcontext

    precision = getcontext().prec

    def atan_inverse(denominator: int) -> Decimal:
        inverse = Decimal(1) / Decimal(denominator)
        inverse_square = inverse * inverse
        term = inverse
        total = term
        ordinal = 1
        cutoff = Decimal(10) ** Decimal(-(precision + 8))
        while True:
            term *= -inverse_square
            addend = term / Decimal(2 * ordinal + 1)
            total += addend
            if abs(addend) <= cutoff:
                return total
            ordinal += 1

    return Decimal(16) * atan_inverse(5) - Decimal(4) * atan_inverse(239)


def _decimal_sin_cos(value: Decimal) -> tuple[Decimal, Decimal]:
    pi = _decimal_pi()
    half_pi = pi / Decimal(2)
    quadrant = int((value / half_pi).to_integral_value(rounding=ROUND_HALF_EVEN))
    reduced = value - Decimal(quadrant) * half_pi
    sine = reduced
    cosine = Decimal(1)
    sine_term = reduced
    cosine_term = Decimal(1)
    for ordinal in range(1, 512):
        sine_term *= -(reduced * reduced) / Decimal((2 * ordinal) * (2 * ordinal + 1))
        cosine_term *= -(reduced * reduced) / Decimal((2 * ordinal - 1) * (2 * ordinal))
        sine += sine_term
        cosine += cosine_term
        if abs(sine_term) <= Decimal(10) ** Decimal(-PRECISION_DIGITS - 8) and abs(cosine_term) <= Decimal(10) ** Decimal(-PRECISION_DIGITS - 8):
            break
    quadrant %= 4
    if quadrant == 0:
        return sine, cosine
    if quadrant == 1:
        return cosine, -sine
    if quadrant == 2:
        return -sine, -cosine
    return -cosine, sine


def _decimal_sinh_cosh(value: Decimal) -> tuple[Decimal, Decimal]:
    positive = value.exp()
    negative = (-value).exp()
    return (positive - negative) / Decimal(2), (positive + negative) / Decimal(2)


def _kick_bound(omega: Decimal, duration: Decimal) -> Decimal:
    if duration == 0:
        return Decimal(1)
    return (Decimal(2) + (omega * duration) ** 2).sqrt()


def _schedule(schedule: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    stages = schedule.get("stages")
    _require(schedule.get("schema") == W3_STAGE_SCHEDULE_SCHEMA and isinstance(stages, list) and len(stages) == 7, "W3 schedule is not the seven-stage release schedule")
    _require([row.get("ordinal") for row in stages] == list(range(1, 8)), "W3 schedule ordinals are not ordered")
    durations = [_decode(row.get("duration_s"), name=f"stage {row.get('ordinal')} duration") for row in stages]
    _require(abs(durations[1] - durations[5]) <= math.ulp(max(1.0, durations[1], durations[5])), "W3 schedule is not symmetric")
    _require(abs(durations[2] - durations[4]) <= math.ulp(max(1.0, durations[2], durations[4])), "W3 spectral half stages are not symmetric")
    return tuple(_plain(row) for row in stages)


def _artifact_identity(transport: Any, supplied: Mapping[str, Any] | None) -> dict[str, Any]:
    if supplied is not None:
        identity = _plain(supplied)
        _require(isinstance(identity, Mapping), "accepted W3 artifact identity must be an object")
        return dict(identity)
    return {
        "schema": W3_ARTIFACT_IDENTITY_SCHEMA,
        "contract_root_sha256": str(transport.contract_root_sha256),
        "profile_sha256": str(transport.profile_sha256),
        "semantic_sha256": str(transport.transport_semantic_sha256),
        "source_identity_sha256": None,
    }


def _consumed_subhashes(geometry: Any, transport: Any, schedule_hash: str) -> list[dict[str, str]]:
    return [
        {"name": "w2_contract_root", "sha256": str(geometry.contract_root_sha256)},
        {"name": "w2_geometry_profile", "sha256": str(geometry.profile_sha256)},
        {"name": "w2_geometry_contract", "sha256": str(geometry.geometry_contract_sha256)},
        {"name": "w2_operator_semantic", "sha256": str(geometry.operator_semantic_sha256)},
        {"name": "w3_contract_root", "sha256": str(transport.contract_root_sha256)},
        {"name": "w3_transport_profile", "sha256": str(transport.profile_sha256)},
        {"name": "w3_transport_semantic", "sha256": str(transport.transport_semantic_sha256)},
        {"name": "w3_stage_schedule", "sha256": schedule_hash},
    ]


def derive_intrinsic_w3_enclosures(*, geometry: Any, transport: Any) -> dict[str, Any]:
    """Derive corrected W3 bounds from complete per-scale signed FFT spectra."""
    try:
        validated = validate_w3_transport_profile(transport, geometry=geometry)
    except Exception as exc:
        raise NumericalCertificateError(f"W3 profile validation failed: {exc}") from exc
    semantic, parameters = _semantic_and_parameters(validated)
    rows = _scale_rows(geometry)
    schedule = _plain(W3_G3_STAGE_SCHEDULE)
    stages = _schedule(schedule)
    schedule_hash = canonical_hash(schedule, W3_STAGE_SCHEDULE_SCHEMA)
    execution = semantic.get("execution_contract", {})
    if isinstance(execution, Mapping) and execution.get("stage_schedule_sha256") is not None:
        _require(execution["stage_schedule_sha256"] == schedule_hash, "W3 semantic schedule hash mismatch")
    state_layout = semantic.get("state_layout", {})
    workspace = semantic.get("workspace", {})
    _require(isinstance(state_layout, Mapping) and isinstance(workspace, Mapping), "W3 layout/workspace semantics are missing")
    dtype = str(state_layout.get("dtype", ""))
    backend = str(state_layout.get("device", ""))
    _require(dtype and backend, "W3 state dtype/device are missing")
    scale_count = int(state_layout.get("scale_count", len(rows)))
    component_count = int(state_layout.get("component_count", 0))
    mode_count = int(state_layout.get("mode_count", 0))
    _require(scale_count == len(rows) and component_count > 0 and mode_count > 0, "W3 state layout does not match W2 scales")
    geometry_payload = _plain(getattr(geometry, "payload", {}))
    storage = geometry_payload.get("geometry_contract", {}).get("storage", {})
    batch_limit = int(storage.get("batch_limit", 1))
    _require(batch_limit > 0, "W2 batch limit is invalid")
    h_tag = schedule.get("h_s")
    h = _decimal(h_tag, name="W3 h")
    h_min_tag = _param(semantic, parameters, "h_min_s")
    h_max_tag = _param(semantic, parameters, "h_max_s")
    h_min = _decimal(h_min_tag, name="W3 h_min")
    h_max = _decimal(h_max_tag, name="W3 h_max")
    _require(Decimal(0) < h_min == h <= h_max, "W3 schedule is not the lower endpoint of its accepted clock interval")
    phi = _decimal(_param(semantic, parameters, "phi"), name="W3 phi")
    amplitude_cap = _decimal(_param(semantic, parameters, "candidate_amplitude_cap"), name="W3 amplitude cap")
    rho_floor = _decimal(_param(semantic, parameters, "rho_floor"), name="W3 rho floor")
    tolerance = _decimal(_param(semantic, parameters, "candidate_numerical_tolerance"), name="W3 tolerance")
    c_values = tuple(_decimal(value, name=f"c_D[{index}]") for index, value in enumerate(_param(semantic, parameters, "c_D_m_per_s")))
    omega_values = tuple(_decimal(value, name=f"omega_D[{index}]") for index, value in enumerate(_param(semantic, parameters, "omega_D_rad_per_s")))
    gamma_values = tuple(_decimal(value, name=f"gamma_D[{index}]") for index, value in enumerate(_param(semantic, parameters, "gamma_D_per_s")))
    kappa_values = tuple(_decimal(value, name=f"kappa_D[{index}]") for index, value in enumerate(_param(semantic, parameters, "kappa_D")))
    _require(len(c_values) == scale_count and len(omega_values) == scale_count and len(gamma_values) == scale_count and len(kappa_values) == scale_count, "W3 parameter count does not match scales")
    _require(all(value >= 0 for value in gamma_values), "W3 damping coefficients must be nonnegative")
    source_budget = int(_decode(_param(semantic, parameters, "source_budget_bytes"), name="W3 source budget"))
    cap = int(workspace.get("byte_cap", 0))
    accounting = str(workspace.get("accounting", ""))
    unbounded = str(workspace.get("unbounded_allocation", ""))
    _require(cap > 0 and accounting and unbounded == "forbidden", "W3 workspace contract is incomplete")
    epsilon = Decimal(2) ** Decimal(-52)
    per_scale_frequency: list[list[Decimal]] = []
    per_scale_max: list[Decimal] = []
    per_scale_branches: list[set[str]] = []
    metric_rows: list[dict[str, Any]] = []
    with localcontext() as context:
        context.prec = PRECISION_DIGITS
        pi = _decimal_pi()
        for scale, row in enumerate(rows):
            ly = _decimal(row["extent_m"]["L_y"], name=f"W2 scale {scale} L_y")
            lx = _decimal(row["extent_m"]["L_x"], name=f"W2 scale {scale} L_x")
            ky_values = tuple((Decimal(2) * pi * Decimal(index)) / ly for index in row["signed_frequency_y"])
            kx_values = tuple((Decimal(2) * pi * Decimal(index)) / lx for index in row["signed_frequency_x"])
            k2_values = [ky * ky + kx * kx for ky in ky_values for kx in kx_values]
            _require(k2_values, f"W2 scale {scale} has no spectral modes")
            per_scale_max.append(max(k2_values))
            frequencies = [(omega_values[scale] * omega_values[scale] + c_values[scale] * c_values[scale] * k2).sqrt() for k2 in k2_values]
            per_scale_frequency.append(frequencies)
            branches: set[str] = set()
            for natural in frequencies:
                branches.add(_oscillator_bound(natural, gamma_values[scale], h / Decimal(2))[0])
            per_scale_branches.append(branches)
            fine_shape = row["oversampling"]["shape_yx"]
            active_sites = Decimal(row["active_site_count"])
            area = _decimal(row["cell_area_m2"], name=f"W2 scale {scale} cell area")
            metric_mass = active_sites * area
            fine_sites = Decimal(fine_shape[0] * fine_shape[1])
            operation_count = Decimal(2 * int(fine_sites) + int(active_sites))
            metric_rows.append({
                "scale": scale,
                "active_shape_yx": row["shape_yx"],
                "active_site_count": row["active_site_count"],
                "spacing_m": row["spacing_m"],
                "extent_m": row["extent_m"],
                "cell_area_m2": row["cell_area_m2"],
                "signed_frequency_y": row["signed_frequency_y"],
                "signed_frequency_x": row["signed_frequency_x"],
                "k2_symbol": "kx^2+ky^2",
                "k2_max_m2": _tag_decimal(per_scale_max[-1]),
                "metric_mass_m2": _tag_decimal(metric_mass),
                "metric_projection_gain": _outward(Decimal(1), Decimal(1)),
                "oversampling": row["oversampling"],
                "projection_operation_count": int(operation_count),
                "projection_roundtrip_abs": _nonnegative_interval(operation_count * epsilon),
            })
        differential_domain_cap = Decimal(2).sqrt() * (Decimal(1) + abs(phi)) * amplitude_cap
        stage_records: list[dict[str, Any]] = []
        stage_bounds: list[Decimal] = []
        for stage in stages:
            duration = _decimal(stage["duration_s"], name=f"stage {stage['ordinal']} duration")
            duration_ratio = duration / h
            duration_min = duration_ratio * h_min
            duration_max = duration_ratio * h_max
            name = str(stage.get("name", ""))
            if "propagation" in name or "spectral" in name:
                bounds = []
                branches = []
                for scale, frequencies in enumerate(per_scale_frequency):
                    values = [
                        Decimal(2).sqrt()
                        if natural > 0
                        else (Decimal(2) + duration_max * duration_max).sqrt()
                        for natural in frequencies
                    ]
                    bounds.append(max(values))
                    branches.append(sorted(per_scale_branches[scale]))
                bound = max(bounds)
            elif "kick" in name:
                bound = max(
                    _kick_bound(
                        Decimal(3) * abs(kappa_values[scale]) * differential_domain_cap * differential_domain_cap,
                        duration_max,
                    )
                    for scale in range(scale_count)
                )
                branches = [[] for _ in rows]
            else:
                bound = Decimal(1)
                branches = [[] for _ in rows]
            stage_bounds.append(bound)
            stage_records.append({
                "ordinal": stage["ordinal"],
                "name": name,
                "duration_s": stage["duration_s"],
                "duration_interval_s": {"minimum": _tag_decimal(duration_min), "maximum": _tag_decimal(duration_max)},
                "branch": "duration-uniform-energy-norm-damped-oscillator" if "propagation" in name or "spectral" in name else "identity-or-force-kick",
                "branches_by_scale": branches,
                "amplification": _outward(Decimal(1), bound),
            })
        full_factor = Decimal(1)
        for bound in stage_bounds:
            full_factor *= bound
        raw_cap = amplitude_cap / full_factor
        d_cap = (Decimal(2).sqrt() * (Decimal(1) + abs(phi))) * raw_cap
        max_frequency = max(max(frequencies) for frequencies in per_scale_frequency)
        velocity_cap = d_cap * max(Decimal(1), max_frequency)
        weight = Decimal(1) / (Decimal(1) + phi * phi)
        energy_by_scale: list[Decimal] = []
        damping_by_scale: list[Decimal] = []
        for scale, row in enumerate(rows):
            area = _decimal(row["cell_area_m2"], name=f"W2 scale {scale} cell area")
            mass = Decimal(row["active_site_count"]) * area
            energy_by_scale.append(
                weight
                * mass
                * (
                    velocity_cap * velocity_cap
                    + (c_values[scale] * c_values[scale] * per_scale_max[scale] + omega_values[scale] * omega_values[scale]) * d_cap * d_cap
                    + abs(kappa_values[scale]) * d_cap ** 4 / Decimal(2)
                )
                / Decimal(2)
            )
            damping_by_scale.append(weight * gamma_values[scale] * mass * velocity_cap * velocity_cap * h_max)
        energy_upper = sum(energy_by_scale, Decimal(0))
        damping_upper = sum(damping_by_scale, Decimal(0))
        projection_upper = max((Decimal(row["projection_operation_count"]) * epsilon for row in metric_rows), default=Decimal(0))
        layout_width = component_count * mode_count
        shape_prefix = [scale_count, layout_width]
        workspace_max_shape = [scale_count, layout_width, batch_limit]
        state_bytes = math.prod(workspace_max_shape) * 8
        fine_bytes = sum(int(row["oversampling"]["shape_yx"][0]) * int(row["oversampling"]["shape_yx"][1]) for row in rows) * batch_limit * 16
        active_bytes = sum(int(row["active_site_count"]) for row in rows) * batch_limit * 16
        workspace_peak = state_bytes + fine_bytes + active_bytes
        _require(workspace_peak <= cap, "current W3 workspace bound exceeds declared cap")
        closure = (energy_upper + damping_upper + projection_upper + Decimal(1)) * epsilon + tolerance
        max_k2 = max(per_scale_max)
        return {
            "schema": NUMERICAL_DERIVATION_SCHEMA,
            "precision": {"decimal_digits": PRECISION_DIGITS, "precision_bits_lower_bound": 256, "rounding": ROUNDING_MODE},
            "inputs": {
                "w2_parent": _plain(getattr(validated, "parent_w2", W2_PARENT_RECORD)),
                "w2_profile_sha256": str(geometry.profile_sha256),
                "w2_contract_root_sha256": str(geometry.contract_root_sha256),
                "w2_geometry_contract_sha256": str(geometry.geometry_contract_sha256),
                "w2_operator_semantic_sha256": str(geometry.operator_semantic_sha256),
                "w3_profile_sha256": str(validated.profile_sha256),
                "w3_contract_root_sha256": str(validated.contract_root_sha256),
                "w3_transport_semantic_sha256": str(validated.transport_semantic_sha256),
                "w3_stage_schedule_sha256": schedule_hash,
                "state_layout": {
                    "layout_id": state_layout.get("layout_id"),
                    "shape_prefix": shape_prefix,
                    "batch_limit": batch_limit,
                    "workspace_max_shape": workspace_max_shape,
                    "component_count": component_count,
                    "mode_count": mode_count,
                    "dtype": dtype,
                    "device": backend,
                    "endianness": state_layout.get("endianness"),
                },
                "active_shapes_yx": [row["shape_yx"] for row in rows],
                "active_site_counts": [row["active_site_count"] for row in rows],
                "per_scale": metric_rows,
                "h_s": h_tag,
                "h_min_s": h_min_tag,
                "h_max_s": h_max_tag,
                "dtype": dtype,
                "backend": backend,
                "amplitude_cap": _tag_decimal(amplitude_cap),
                "rho_floor": _tag_decimal(rho_floor),
                "source_byte_budget": source_budget,
                "workspace_byte_cap": cap,
                "workspace_accounting": accounting,
                "workspace_unbounded_allocation": unbounded,
            },
            "schedule_enclosure": stage_records,
            "enclosures": {
                "laplacian_abs_max_m2": [_nonnegative_interval(value) for value in per_scale_max],
                "spectral_frequency_rad_per_s": [_nonnegative_interval(max(values)) for values in per_scale_frequency],
                "spectral_frequency_rad_per_s_by_mode": [[_nonnegative_interval(value) for value in values] for values in per_scale_frequency],
                "half_stage_amplification": [row["amplification"] for row in stage_records if "propagation" in row["name"] or "spectral" in row["name"]],
                "stage_amplification": [row["amplification"] for row in stage_records],
                "full_step_amplification": _outward(Decimal(1), full_factor),
                "raw_component_admission_abs": _nonnegative_interval(raw_cap),
                "differential_amplitude_abs": _nonnegative_interval(d_cap),
                "differential_velocity_abs": _nonnegative_interval(velocity_cap),
                "energy_nonnegative": _nonnegative_interval(energy_upper),
                "damping_work_magnitude": _nonnegative_interval(damping_upper),
                "source_work": _nonnegative_interval(Decimal(0)),
                "projection_roundtrip_abs": _nonnegative_interval(projection_upper),
                "metric_projection_gain": [_outward(Decimal(1), Decimal(1)) for _ in rows],
                "workspace_peak_bytes": {"lower": str(workspace_peak), "upper": str(workspace_peak)},
                "workspace_byte_cap": cap,
                "work_closure_abs": _nonnegative_interval(closure),
                "nonlinear_coefficient_abs": [_nonnegative_interval(abs(value)) for value in kappa_values],
            },
            "positivity": {
                "metric_cell_area_positive": all(_decode(row["cell_area_m2"], name="metric area") > 0 for row in rows),
                "d_coordinate_weight_positive": weight > 0,
                "rho_floor_positive": rho_floor > 0,
                "wave_speed_squared_nonnegative": all(value >= 0 for value in c_values),
                "damping_nonnegative": all(value >= 0 for value in gamma_values),
                "energy_terms_nonnegative": True,
                "source_admission": "only-empty-source" if source_budget == 0 else "profile-budgeted-source",
                "nonlinear_projection": "metric-adjoint-complete-frequency",
            },
            "derivation_formulae": {
                "laplacian": "lambda(k)=-(kx^2+ky^2), k_axis=2*pi*n_axis/L_axis",
                "spectral_maximum": "max over every signed W2 FFT bin on each active (Ny,Nx) sheet",
                "frequency": "Omega_D,s(k)=sqrt(omega_D,s^2+c_D,s^2*(kx^2+ky^2))",
                "damped_branches": "exact underdamped/critical/overdamped analytic 2x2 branch classification",
                "half_amplification": "duration-uniform energy-normalized Frobenius enclosure over the complete accepted clock interval",
                "force_kick": "metric-normalized Frobenius enclosure with cubic-force Jacobian norm <=3*abs(kappa_D,s)*D_domain^2 at the maximum accepted stage duration",
                "raw_admission": "amplitude_cap/product(stage_amplification)",
                "metric": "W_s=dx_s*dy_s*I and ||I_s R_s||_(W_s)=1",
                "projection": "complete-signed-frequency injection/restriction with metric-adjoint projection",
                "energy": "sum_s w_D*N_s*dx_s*dy_s*(|V_D|^2+(c_D,s^2*k2_max,s+omega_D,s^2)*|D|^2+abs(kappa_D,s)*|D|^4/2)/2",
                "workspace": "state bytes plus active and oversampled complex workspaces, bounded by semantic workspace.byte_cap",
                "rounding": "outward-nextafter-f64 after Decimal derivation",
            },
            "consumed_parameter_check": {
                "phi": _tag_decimal(phi),
                "c_D_m_per_s": [_tag_decimal(value) for value in c_values],
                "omega_D_rad_per_s": [_tag_decimal(value) for value in omega_values],
                "gamma_D_per_s": [_tag_decimal(value) for value in gamma_values],
                "kappa_D": [_tag_decimal(value) for value in kappa_values],
                "max_k2_m2": _tag_decimal(max_k2),
                "branches": [sorted(branches) for branches in per_scale_branches],
            },
        }


def build_numerical_certificate(*, geometry: Any, transport: Any, accepted_w3_artifact_identity: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    validated = validate_w3_transport_profile(transport, geometry=geometry)
    derivation = derive_intrinsic_w3_enclosures(geometry=geometry, transport=validated)
    schedule_hash = derivation["inputs"]["w3_stage_schedule_sha256"]
    consumed = _consumed_subhashes(geometry, validated, schedule_hash)
    parent = _plain(getattr(validated, "parent_w2", W2_PARENT_RECORD))
    artifact_identity = _artifact_identity(validated, accepted_w3_artifact_identity)
    chain_id = canonical_hash({"w2_parent": parent, "consumed": consumed, "accepted_w3_artifact_identity": artifact_identity}, NUMERICAL_CERTIFICATE_DOMAIN)
    layout = derivation["inputs"]["state_layout"]
    guard = {
        "schema": NUMERICAL_GUARD_SCHEMA,
        "dtype": layout["dtype"],
        "backend": layout["device"],
        "raw_layout": layout,
        "active_shapes_yx": derivation["inputs"]["active_shapes_yx"],
        "raw_component_admission_abs": derivation["enclosures"]["raw_component_admission_abs"]["upper"],
        "source_byte_budget": int(derivation["inputs"]["source_byte_budget"]),
        "workspace_byte_cap": int(derivation["inputs"]["workspace_byte_cap"]),
        "stage_schedule_sha256": schedule_hash,
        "reject_before_mutation": True,
        "no_interval_widening": True,
        "no_clipping": True,
        "no_substitute_derivation": True,
    }
    root: dict[str, Any] = {
        "schema": NUMERICAL_CERTIFICATE_SCHEMA,
        "certificate_chain_id": chain_id,
        "chain_ordinal": 0,
        "parent_certificate_sha256": None,
        "profile_sha256": validated.profile_sha256,
        "contract_root_sha256": validated.contract_root_sha256,
        "transport_semantic_sha256": validated.transport_semantic_sha256,
        "operator_semantic_sha256": geometry.operator_semantic_sha256,
        "execution_schedule_sha256": schedule_hash,
        "w2_parent": parent,
        "accepted_w3_artifact_identity": artifact_identity,
        "consumed_semantic_subhashes": consumed,
        "offline_derivation": derivation,
        "online_guard_contract": guard,
        "complete_section_inventory": [],
        "chain_status": "provisional",
    }
    root["self_sha256"] = canonical_hash(root, NUMERICAL_CERTIFICATE_DOMAIN)
    section = {
        "schema": NUMERICAL_SECTION_SCHEMA,
        "section_id": "intrinsic-w3-numerics",
        "owning_package": "W3N",
        "gate": "G3N",
        "required": True,
        "profile_sha256": validated.profile_sha256,
        "contract_root_sha256": validated.contract_root_sha256,
        "transport_semantic_sha256": validated.transport_semantic_sha256,
        "operator_semantic_sha256": geometry.operator_semantic_sha256,
        "execution_schedule_sha256": schedule_hash,
        "offline_derivation_sha256": canonical_hash(derivation, NUMERICAL_DERIVATION_SCHEMA),
        "online_guard_sha256": canonical_hash(guard, NUMERICAL_GUARD_SCHEMA),
    }
    extension = build_certificate_extension(
        parent=root,
        parent_schema=NUMERICAL_CERTIFICATE_SCHEMA,
        parent_domain=NUMERICAL_CERTIFICATE_DOMAIN,
        extension_schema=CERTIFICATE_EXTENSION_SCHEMA,
        extension_domain=NUMERICAL_EXTENSION_DOMAIN,
        section_body=section,
        section_schema=NUMERICAL_SECTION_SCHEMA,
        section_domain=NUMERICAL_SECTION_SCHEMA,
        owning_package="W3N",
        gate="G3N",
        chain_status="final",
        final_certificate_identity=True,
        extra_fields={
            "consumed_semantic_subhashes": consumed,
            "accepted_w3_artifact_identity": artifact_identity,
        },
    )
    return root, extension


def build_registry_extension(*, parent_registry_sha256: str, parent_w1_run_id: str) -> dict[str, Any]:
    entries = [
        {"schema": NUMERICAL_CERTIFICATE_SCHEMA, "max_bytes": 262144, "lifecycle": "artifact", "semantic_parents": ["state_contract_sha256", "backend_capacity_sha256"]},
        {"schema": CERTIFICATE_EXTENSION_SCHEMA, "max_bytes": 131072, "lifecycle": "artifact", "semantic_parents": ["state_contract_sha256", "backend_capacity_sha256"]},
        {"schema": NUMERICAL_GUARD_RECEIPT_SCHEMA, "max_bytes": 32768, "lifecycle": "receipt", "semantic_parents": ["state_contract_sha256", "backend_capacity_sha256"]},
    ]
    record = {"schema": CERTIFICATE_REGISTRY_EXTENSION_SCHEMA, "parent_registry_sha256": str(parent_registry_sha256), "parent_w1_run_id": str(parent_w1_run_id), "entries": sorted(entries, key=lambda item: item["schema"])}
    record["self_sha256"] = canonical_hash(record, NUMERICAL_EXTENSION_REGISTRY_DOMAIN)
    return record


def _layout_from_contract(contract: Mapping[str, Any]) -> tuple[list[int], int, int, int, list[int]]:
    raw_layout = contract.get("raw_layout")
    _require(isinstance(raw_layout, Mapping), "guard raw layout is missing")
    shape_prefix = raw_layout.get("shape_prefix")
    batch_limit = raw_layout.get("batch_limit")
    _require(
        isinstance(shape_prefix, list)
        and len(shape_prefix) == 2
        and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in shape_prefix),
        "guard raw layout shape prefix is invalid",
    )
    _require(isinstance(batch_limit, int) and not isinstance(batch_limit, bool) and batch_limit > 0, "guard batch limit is invalid")
    component_count = int(raw_layout.get("component_count", 0))
    mode_count = int(raw_layout.get("mode_count", 0))
    _require(component_count > 0 and mode_count > 0, "guard component/mode layout is invalid")
    active_shapes = contract.get("active_shapes_yx")
    _require(isinstance(active_shapes, list) and len(active_shapes) == shape_prefix[0], "guard active per-scale layout is missing")
    active_sites: list[int] = []
    for item in active_shapes:
        _require(isinstance(item, list) and len(item) == 2 and all(isinstance(n, int) and n > 0 for n in item), "guard active shape is invalid")
        active_sites.append(item[0] * item[1])
    _require(shape_prefix[1] == component_count * mode_count and all(n <= mode_count for n in active_sites), "guard packed layout is invalid")
    return list(shape_prefix), batch_limit, component_count, mode_count, active_sites


def _raw_state_status(
    raw: bytes,
    *,
    shape_prefix: Sequence[int],
    batch_limit: int,
    component_count: int,
    mode_count: int,
    active_sites: Sequence[int],
) -> tuple[bool, bool, float, bool, list[int]]:
    element_stride = math.prod(shape_prefix)
    if len(raw) % 8 or element_stride <= 0:
        return False, False, 0.0, False, [*shape_prefix, 0]
    element_count = len(raw) // 8
    if element_count % element_stride:
        return False, False, 0.0, False, [*shape_prefix, 0]
    batch = element_count // element_stride
    shape = [*shape_prefix, batch]
    if not 1 <= batch <= batch_limit:
        return False, False, 0.0, False, shape
    maximum = 0.0
    finite = True
    for (value,) in struct.iter_unpack("<d", raw):
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
            finite = False
            maximum = math.inf
            break
        maximum = max(maximum, abs(value))
    tails_zero = True
    scales, packed_width = shape_prefix
    for scale in range(scales):
        active = active_sites[scale]
        for component in range(component_count):
            for mode in range(active, mode_count):
                for batch_lane in range(batch):
                    offset = ((scale * packed_width + component * mode_count + mode) * batch + batch_lane) * 8
                    if raw[offset : offset + 8] != b"\x00" * 8:
                        tails_zero = False
                        break
                if not tails_zero:
                    break
            if not tails_zero:
                break
        if not tails_zero:
            break
    return True, finite, maximum, tails_zero, shape


def evaluate_online_guard(
    certificate: Mapping[str, Any],
    *,
    raw_state: bytes,
    source: Any = None,
    dtype: str | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    """Check only the sealed layout/cap/source contract before mutation."""
    if not isinstance(certificate, Mapping) or certificate.get("schema") != NUMERICAL_CERTIFICATE_SCHEMA:
        raise NumericalCertificateError("online guard requires a numerical-certificate root")
    plain_certificate = _plain(certificate)
    expected = canonical_hash({key: value for key, value in plain_certificate.items() if key != "self_sha256"}, NUMERICAL_CERTIFICATE_DOMAIN)
    _require(plain_certificate.get("self_sha256") == expected, "online guard certificate identity mismatch")
    contract = plain_certificate.get("online_guard_contract")
    _require(isinstance(contract, Mapping) and contract.get("schema") == NUMERICAL_GUARD_SCHEMA, "online guard contract is missing")
    shape_prefix, batch_limit, component_count, mode_count, active_sites = _layout_from_contract(contract)
    layout_valid, finite, maximum, tails_zero, shape = _raw_state_status(
        raw_state,
        shape_prefix=shape_prefix,
        batch_limit=batch_limit,
        component_count=component_count,
        mode_count=mode_count,
        active_sites=active_sites,
    )
    threshold = _decode(contract.get("raw_component_admission_abs"), name="raw guard threshold")
    expected_dtype = str(contract.get("dtype"))
    expected_backend = str(contract.get("backend"))
    observed_dtype = expected_dtype if dtype is None else str(dtype)
    observed_backend = expected_backend if backend is None else str(backend)
    source_bytes = 0 if source is None else len(canonical_json_bytes(_plain(source)))
    accepted = observed_dtype == expected_dtype and observed_backend == expected_backend and source_bytes <= int(contract.get("source_byte_budget", -1)) and layout_valid and finite and tails_zero and maximum <= threshold
    if observed_dtype != expected_dtype:
        reason = "dtype-mismatch"
    elif observed_backend != expected_backend:
        reason = "backend-mismatch"
    elif source_bytes > int(contract.get("source_byte_budget", -1)):
        reason = "source-budget-exceeded"
    elif not layout_valid:
        reason = "raw-layout-mismatch"
    elif not finite:
        reason = "nonfinite-or-negative-zero-raw-state"
    elif not tails_zero:
        reason = "inactive-tail-nonzero"
    elif maximum > threshold:
        reason = "raw-component-envelope-exceeded"
    else:
        reason = "accepted"
    receipt = {
        "schema": NUMERICAL_GUARD_RECEIPT_SCHEMA,
        "certificate_sha256": plain_certificate["self_sha256"],
        "guard_contract_sha256": canonical_hash(_plain(contract), NUMERICAL_GUARD_SCHEMA),
        "raw_state_sha256": _raw_hash(raw_state, shape=shape),
        "raw_state_byte_count": len(raw_state),
        "raw_layout": {
            "shape": shape,
            "batch_limit": batch_limit,
            "component_count": component_count,
            "mode_count": mode_count,
            "layout_valid": layout_valid,
            "inactive_tail_zero": tails_zero,
        },
        "dtype": observed_dtype,
        "backend": observed_backend,
        "source_byte_count": source_bytes,
        "source_byte_budget": int(contract.get("source_byte_budget", -1)),
        "workspace_byte_cap": int(contract.get("workspace_byte_cap", -1)),
        "raw_component_max_abs": _f64(maximum if math.isfinite(maximum) else float.fromhex("0x1.fffffffffffffp+1023")),
        "raw_component_admission_abs": contract["raw_component_admission_abs"],
        "stage_schedule_sha256": contract["stage_schedule_sha256"],
        "rounding_budget_sha256": canonical_hash(plain_certificate["offline_derivation"]["enclosures"]["work_closure_abs"], NUMERICAL_DERIVATION_SCHEMA),
        "decision": "ACCEPT" if accepted else "REJECT",
        "reason": reason,
        "mutation_permitted": accepted,
    }
    receipt["self_sha256"] = canonical_hash(receipt, NUMERICAL_GUARD_DOMAIN)
    return receipt


def transition_v3_transport_guarded(
    state: Any,
    *,
    geometry_profile: Any,
    transport_profile: Any,
    certificate: Mapping[str, Any],
    source: Any = None,
    duration_s: float | None = None,
    dtype: str | None = None,
    backend: str | None = None,
) -> Any:
    """Reject before allocation/delegation when the immutable guard fails."""
    from cassi_qi_field import QiFlowStepW3, transition_v3_transport

    guard = evaluate_online_guard(
        certificate,
        raw_state=raw_state_bytes_from_field(state.field),
        source=source,
        dtype=dtype,
        backend=backend,
    )
    if guard["decision"] != "ACCEPT":
        return QiFlowStepW3(
            predecessor=state,
            candidate=None,
            committable=False,
            diagnostics=None,
            ledger=None,
            receipt=MappingProxyType({
                "schema": "cassi.qi-flow-transport-w3-receipt.v1",
                "status": "REJECTED",
                "parents": MappingProxyType({}),
                "failure_reason": f"W3N numerical guard rejected predecessor: {guard['reason']}",
                "committable": False,
                "numerical_guard": MappingProxyType(dict(guard)),
                "guarded_entry_required_for": ["W4+"],
            }),
            failure_reason=str(guard["reason"]),
        )
    step = transition_v3_transport(state, geometry_profile=geometry_profile, transport_profile=transport_profile, duration_s=duration_s)
    receipt_data = dict(step.receipt or {})
    receipt_data["numerical_guard"] = MappingProxyType(dict(guard))
    receipt_data["guarded_entry_required_for"] = ["W4+"]
    return QiFlowStepW3(
        predecessor=step.predecessor,
        candidate=step.candidate,
        committable=step.committable,
        diagnostics=step.diagnostics,
        ledger=step.ledger,
        receipt=MappingProxyType(receipt_data),
        failure_reason=step.failure_reason,
    )


__all__ = [
    "CERTIFICATE_EXTENSION_SCHEMA", "CERTIFICATE_REGISTRY_EXTENSION_SCHEMA",
    "NUMERICAL_CERTIFICATE_SCHEMA", "NUMERICAL_CERTIFICATE_DOMAIN",
    "NUMERICAL_DERIVATION_SCHEMA", "NUMERICAL_EXTENSION_DOMAIN",
    "NUMERICAL_GUARD_RECEIPT_SCHEMA", "NUMERICAL_RAW_STATE_DOMAIN",
    "NUMERICAL_SECTION_SCHEMA", "NumericalCertificateError",
    "G3N_EXECUTED_CONTROL_IDS", "build_certificate_extension",
    "build_numerical_certificate", "build_registry_extension",
    "derive_intrinsic_w3_enclosures", "evaluate_online_guard",
    "raw_state_bytes_from_field", "transition_v3_transport_guarded",
    "validate_certificate_extension",
]
