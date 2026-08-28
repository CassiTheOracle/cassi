"""Independent verifier for corrected W3N/G3N periodic-FFT2 artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
W1_ROOT = ROOT / "_diag" / "cassi-qi-flow-w1-final"
W2_ROOT = ROOT / "_diag" / "cassi-qi-flow-w2-periodic-fft2-final"
W3_ROOT = ROOT / "_diag" / "cassi-qi-flow-w3-periodic-fft2-final"
INDEX_SCHEMA = "cassi.qi-flow-w3n-periodic-fft2-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w3n-periodic-fft2-artifact.v1"
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w3n-periodic-fft2-source-identity.v1"
GUARD_REPLAY_SCHEMA = "cassi.qi-flow-w3n-guard-replay.v2"
CONTROLS_SCHEMA = "cassi.qi-flow-w3n-controls.v2"
CANDIDATE_SCHEMA = "cassi.qi-flow-g3n-candidate.v2"
CERTIFICATE_SCHEMA = "cassi.qi-flow-numerical-certificate.v1"
DERIVATION_SCHEMA = "cassi.qi-flow-w3n-offline-derivation.v1"
SECTION_SCHEMA = "cassi.qi-flow-w3n-intrinsic-section.v1"
EXTENSION_SCHEMA = "cassi.qi-flow-certificate-extension.v1"
GUARD_SCHEMA = "cassi.qi-flow-numerical-guard.v1"
GUARD_RECEIPT_SCHEMA = "cassi.qi-flow-numerical-guard-receipt.v1"
REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry-extension.v1"
CERTIFICATE_DOMAIN = "cassi.qi-flow-w3n-certificate.v1"
EXTENSION_DOMAIN = "cassi.qi-flow-w3n-extension.v1"
REGISTRY_DOMAIN = "cassi.qi-flow-w3n-registry-extension.v1"
GUARD_DOMAIN = "cassi.qi-flow-w3n-guard.v1"
RAW_DOMAIN = "cassi.qi-flow-w3n-raw-state.v1"
W3_STAGE_SCHEMA = "cassi.qi-flow-g3-stage-schedule.v1"
PRECISION_DIGITS = 80
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


class NumericalCertificateVerificationError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise NumericalCertificateVerificationError(message)


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in rows:
        if key in value:
            _fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_float(value: str) -> Any:
    _fail(f"JSON numeric literal is forbidden: {value}")


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except NumericalCertificateVerificationError:
        raise
    except Exception as exc:
        raise NumericalCertificateVerificationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        _fail(f"{path} is not a JSON object")
    return value


def _bytes(value: Any) -> bytes:
    def walk(item: Any) -> None:
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, list):
            for child in item:
                walk(child)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    _fail("canonical object key is not a string")
                walk(child)
            return
        _fail(f"non-canonical value type: {type(item).__name__}")

    walk(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8")
    payload = _bytes(value)
    return hashlib.sha256(len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload).hexdigest()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _f64(value: Any, *, name: str) -> float:
    if not isinstance(value, str) or not value.startswith("f64:") or len(value) != 20:
        _fail(f"{name} is not canonical f64")
    try:
        raw = bytes.fromhex(value[4:])
    except ValueError as exc:
        raise NumericalCertificateVerificationError(f"{name} has invalid f64 hex") from exc
    decoded = struct.unpack(">d", raw)[0]
    if not math.isfinite(decoded) or (decoded == 0.0 and math.copysign(1.0, decoded) < 0.0):
        _fail(f"{name} is non-finite or negative zero")
    return decoded


def _tag(value: float) -> str:
    if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
        _fail("cannot tag non-finite or negative-zero f64")
    return "f64:" + struct.pack(">d", float(value)).hex()


def _dec(value: Any, *, name: str) -> Decimal:
    return Decimal.from_float(_f64(value, name=name))


def _tag_dec(value: Decimal) -> str:
    return _tag(float(value))


def _outward(lower: Decimal, upper: Decimal) -> dict[str, str]:
    if lower > upper:
        _fail("inverted enclosure")
    return {"lower": _tag(math.nextafter(float(lower), -math.inf)), "upper": _tag(math.nextafter(float(upper), math.inf))}


def _nonnegative(upper: Decimal) -> dict[str, str]:
    if upper < 0:
        _fail("negative nonnegative enclosure")
    return {"lower": _tag(0.0), "upper": _tag(math.nextafter(float(upper), math.inf))}


def _pi() -> Decimal:
    from decimal import getcontext

    precision = getcontext().prec

    def atan_inverse(denominator: int) -> Decimal:
        inverse = Decimal(1) / Decimal(denominator)
        square = inverse * inverse
        term = inverse
        total = term
        ordinal = 1
        cutoff = Decimal(10) ** Decimal(-(precision + 8))
        while True:
            term *= -square
            addend = term / Decimal(2 * ordinal + 1)
            total += addend
            if abs(addend) <= cutoff:
                return total
            ordinal += 1

    return Decimal(16) * atan_inverse(5) - Decimal(4) * atan_inverse(239)


def _sin_cos(value: Decimal) -> tuple[Decimal, Decimal]:
    half_pi = _pi() / Decimal(2)
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


def _oscillator_bound(omega: Decimal, gamma: Decimal, duration: Decimal) -> tuple[str, Decimal]:
    if duration == 0:
        return "identity", Decimal(1)
    alpha = gamma / Decimal(2)
    if omega > alpha:
        branch = "underdamped"
        frequency = (omega * omega - alpha * alpha).sqrt()
        sine, cosine = _sin_cos(frequency * duration)
        s_over = sine / frequency
    elif omega == alpha:
        branch = "critical"
        decay = (-alpha * duration).exp()
        a11 = decay * (Decimal(1) + alpha * duration)
        a12 = decay * duration
        a21 = decay * (-(omega * omega) * duration)
        a22 = decay * (Decimal(1) - alpha * duration)
        entries = (a11, omega * a12, a21 / omega if omega else a21, a22)
        return branch, sum(item * item for item in entries).sqrt()
    else:
        branch = "overdamped"
        frequency = (alpha * alpha - omega * omega).sqrt()
        positive = (frequency * duration).exp()
        negative = (-frequency * duration).exp()
        sine = (positive - negative) / Decimal(2)
        cosine = (positive + negative) / Decimal(2)
        s_over = sine / frequency
    decay = (-alpha * duration).exp()
    a11 = decay * (cosine + alpha * s_over)
    a12 = decay * s_over
    a21 = decay * (-(omega * omega) * s_over)
    a22 = decay * (cosine - alpha * s_over)
    entries = (a11, omega * a12, a21 / omega if omega else a21, a22)
    return branch, sum(item * item for item in entries).sqrt()


def _scale_rows(w2: Mapping[str, Any]) -> list[dict[str, Any]]:
    sheets = w2["geometry_contract"]["per_scale_sheets"]
    if not isinstance(sheets, list) or not sheets:
        _fail("W2 per-scale sheet inventory is absent")
    rows = []
    for scale, sheet in enumerate(sheets):
        shape = sheet["active_rectangle"]["shape_yx"]
        spacing = sheet["spacing_m"]
        extent = sheet["extent_m"]
        oversampling = sheet["oversampling"]
        ny, nx = (int(shape[0]), int(shape[1]))
        dy, dx = (_dec(spacing[0], name=f"scale {scale} dy"), _dec(spacing[1], name=f"scale {scale} dx"))
        ly, lx = (_dec(extent[0], name=f"scale {scale} Ly"), _dec(extent[1], name=f"scale {scale} Lx"))
        rows.append({
            "scale": scale,
            "shape_yx": [ny, nx],
            "active_site_count": int(sheet["active_site_count"]),
            "spacing_m": {"dy": _tag_dec(dy), "dx": _tag_dec(dx)},
            "extent_m": {"L_y": _tag_dec(ly), "L_x": _tag_dec(lx)},
            "cell_area_m2": _tag_dec(_dec(sheet["cell_area_m2"], name=f"scale {scale} cell area")),
            "signed_frequency_y": [int(value) for value in sheet["signed_frequency_y"]],
            "signed_frequency_x": [int(value) for value in sheet["signed_frequency_x"]],
            "oversampling": oversampling,
        })
    return rows


def _derive(w2: Mapping[str, Any], w3: Mapping[str, Any], schedule: Mapping[str, Any]) -> dict[str, Any]:
    semantic = w3["semantic"]
    dynamics = semantic["dynamics"]
    layout = semantic["state_layout"]
    workspace = semantic["workspace"]
    rows = _scale_rows(w2)
    scale_count = int(layout["scale_count"])
    component_count = int(layout["component_count"])
    mode_count = int(layout["mode_count"])
    if scale_count != len(rows) or component_count != 9:
        _fail("W3N state layout disagrees with W2 sheets")
    stages = schedule["stages"]
    schedule_core = {key: value for key, value in schedule.items() if key != "stage_schedule_sha256"}
    schedule_hash = _hash(schedule_core, W3_STAGE_SCHEMA)
    if schedule.get("stage_schedule_sha256") != schedule_hash or schedule.get("schema") != W3_STAGE_SCHEMA or len(stages) != 7:
        _fail("W3 stage schedule is not canonical")
    h_tag = schedule["h_s"]
    with localcontext() as context:
        context.prec = PRECISION_DIGITS
        pi = _pi()
        phi = _dec(dynamics["phi"], name="phi")
        c_values = [_dec(value, name="c_D") for value in dynamics["c_D_m_per_s"]]
        omega_values = [_dec(value, name="omega_D") for value in dynamics["omega_D_rad_per_s"]]
        gamma_values = [_dec(value, name="gamma_D_per_s") for value in dynamics["gamma_D_per_s"]]
        kappa_values = [_dec(value, name="kappa_D") for value in dynamics["kappa_D"]]
        h = _dec(h_tag, name="h")
        amplitude_cap = _dec(dynamics["candidate_amplitude_cap"], name="amplitude cap")
        rho_floor = _dec(dynamics["rho_floor"], name="rho floor")
        tolerance = _dec(dynamics["candidate_numerical_tolerance"], name="tolerance")
        source_budget = int(dynamics["source_budget_bytes"])
        if not all(len(values) == scale_count for values in (c_values, omega_values, gamma_values, kappa_values)):
            _fail("W3 per-scale dynamics are incomplete")
        epsilon = Decimal(2) ** Decimal(-52)
        per_scale_frequency: list[list[Decimal]] = []
        per_scale_max: list[Decimal] = []
        per_scale_branches: list[set[str]] = []
        metric_rows: list[dict[str, Any]] = []
        for scale, row in enumerate(rows):
            ly = _dec(row["extent_m"]["L_y"], name=f"scale {scale} Ly")
            lx = _dec(row["extent_m"]["L_x"], name=f"scale {scale} Lx")
            ky_values = tuple(Decimal(2) * pi * Decimal(index) / ly for index in row["signed_frequency_y"])
            kx_values = tuple(Decimal(2) * pi * Decimal(index) / lx for index in row["signed_frequency_x"])
            k2_values = [ky * ky + kx * kx for ky in ky_values for kx in kx_values]
            per_scale_max.append(max(k2_values))
            frequencies = [(omega_values[scale] ** 2 + c_values[scale] ** 2 * k2).sqrt() for k2 in k2_values]
            per_scale_frequency.append(frequencies)
            branches: set[str] = set()
            for natural in frequencies:
                branches.add(_oscillator_bound(natural, gamma_values[scale], h / Decimal(2))[0])
            per_scale_branches.append(branches)
            fine_shape = row["oversampling"]["shape_yx"]
            active_sites = Decimal(row["active_site_count"])
            area = _dec(row["cell_area_m2"], name=f"scale {scale} cell area")
            metric_mass = active_sites * area
            fine_sites = Decimal(int(fine_shape[0]) * int(fine_shape[1]))
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
                "k2_max_m2": _tag_dec(per_scale_max[-1]),
                "metric_mass_m2": _tag_dec(metric_mass),
                "metric_projection_gain": _outward(Decimal(1), Decimal(1)),
                "oversampling": row["oversampling"],
                "projection_operation_count": int(operation_count),
                "projection_roundtrip_abs": _nonnegative(operation_count * epsilon),
            })
        differential_domain_cap = Decimal(2).sqrt() * (Decimal(1) + abs(phi)) * amplitude_cap
        stage_records: list[dict[str, Any]] = []
        stage_bounds: list[Decimal] = []
        for stage in stages:
            name = str(stage["name"])
            duration = _dec(stage["duration_s"], name=f"stage {name} duration")
            if "propagation" in name or "spectral" in name:
                bounds = []
                branches = []
                for scale, frequencies in enumerate(per_scale_frequency):
                    values = [_oscillator_bound(natural, gamma_values[scale], duration)[1] for natural in frequencies]
                    bounds.append(max(values))
                    branches.append(sorted(per_scale_branches[scale]))
                bound = max(bounds)
            elif "kick" in name:
                bound = max((Decimal(2) + (Decimal(3) * abs(kappa_values[scale]) * differential_domain_cap ** 2 * duration) ** 2).sqrt() for scale in range(scale_count))
                branches = [[] for _ in rows]
            else:
                bound = Decimal(1)
                branches = [[] for _ in rows]
            stage_bounds.append(bound)
            stage_records.append({"ordinal": int(stage["ordinal"]), "name": name, "duration_s": stage["duration_s"], "branch": "exact-analytic-damped-oscillator" if "propagation" in name or "spectral" in name else "identity-or-force-kick", "branches_by_scale": branches, "amplification": _outward(Decimal(1), bound)})
        full_factor = Decimal(1)
        for bound in stage_bounds:
            full_factor *= bound
        raw_cap = amplitude_cap / full_factor
        d_cap = Decimal(2).sqrt() * (Decimal(1) + abs(phi)) * raw_cap
        max_frequency = max(max(values) for values in per_scale_frequency)
        velocity_cap = d_cap * max(Decimal(1), max_frequency)
        weight = Decimal(1) / (Decimal(1) + phi * phi)
        energy_by_scale: list[Decimal] = []
        damping_by_scale: list[Decimal] = []
        for scale, row in enumerate(rows):
            mass = Decimal(row["active_site_count"]) * _dec(row["cell_area_m2"], name="cell area")
            energy_by_scale.append(weight * mass * (velocity_cap ** 2 + (c_values[scale] ** 2 * per_scale_max[scale] + omega_values[scale] ** 2) * d_cap ** 2 + abs(kappa_values[scale]) * d_cap ** 4 / Decimal(2)) / Decimal(2))
            damping_by_scale.append(weight * gamma_values[scale] * mass * velocity_cap ** 2 * h)
        energy_upper = sum(energy_by_scale, Decimal(0))
        damping_upper = sum(damping_by_scale, Decimal(0))
        projection_upper = max((Decimal(row["projection_operation_count"]) * epsilon for row in metric_rows), default=Decimal(0))
        batch_limit = int(w2["geometry_contract"]["storage"]["batch_limit"])
        shape_prefix = [scale_count, component_count * mode_count]
        workspace_max_shape = [*shape_prefix, batch_limit]
        state_bytes = math.prod(workspace_max_shape) * 8
        fine_bytes = sum(int(row["oversampling"]["shape_yx"][0]) * int(row["oversampling"]["shape_yx"][1]) for row in rows) * batch_limit * 16
        active_bytes = sum(int(row["active_site_count"]) for row in rows) * batch_limit * 16
        workspace_peak = state_bytes + fine_bytes + active_bytes
        cap = int(workspace["byte_cap"])
        if workspace_peak > cap:
            _fail("independent W3N workspace bound exceeds the W3 cap")
        closure = (energy_upper + damping_upper + projection_upper + Decimal(1)) * epsilon + tolerance
        max_k2 = max(per_scale_max)
        return {
            "schema": DERIVATION_SCHEMA,
            "precision": {"decimal_digits": PRECISION_DIGITS, "precision_bits_lower_bound": 256, "rounding": "decimal-80-directed-nextafter-f64.v1"},
            "inputs": {
                "w2_parent": w3["parent_w2"],
                "w2_profile_sha256": w2["profile_sha256"],
                "w2_contract_root_sha256": w2["contract_root_sha256"],
                "w2_geometry_contract_sha256": w2["geometry_contract_sha256"],
                "w2_operator_semantic_sha256": w2["operator_semantic_sha256"],
                "w3_profile_sha256": w3["profile_sha256"],
                "w3_contract_root_sha256": w3["contract_root_sha256"],
                "w3_transport_semantic_sha256": w3["semantic_sha256"],
                "w3_stage_schedule_sha256": schedule_hash,
                "state_layout": {"layout_id": layout.get("layout_id"), "shape_prefix": shape_prefix, "batch_limit": batch_limit, "workspace_max_shape": workspace_max_shape, "component_count": component_count, "mode_count": mode_count, "dtype": layout["dtype"], "device": layout["device"], "endianness": layout["endianness"]},
                "active_shapes_yx": [row["shape_yx"] for row in rows],
                "active_site_counts": [row["active_site_count"] for row in rows],
                "per_scale": metric_rows,
                "h_s": h_tag,
                "dtype": layout["dtype"],
                "backend": layout["device"],
                "amplitude_cap": _tag_dec(amplitude_cap),
                "rho_floor": _tag_dec(rho_floor),
                "source_byte_budget": source_budget,
                "workspace_byte_cap": cap,
                "workspace_accounting": workspace["accounting"],
                "workspace_unbounded_allocation": workspace["unbounded_allocation"],
            },
            "enclosures": {
                "laplacian_abs_max_m2": [_nonnegative(value) for value in per_scale_max],
                "spectral_frequency_rad_per_s": [_nonnegative(max(values)) for values in per_scale_frequency],
                "spectral_frequency_rad_per_s_by_mode": [[_nonnegative(value) for value in values] for values in per_scale_frequency],
                "half_stage_amplification": [row["amplification"] for row in stage_records if "propagation" in row["name"] or "spectral" in row["name"]],
                "stage_amplification": [row["amplification"] for row in stage_records],
                "full_step_amplification": _outward(Decimal(1), full_factor),
                "raw_component_admission_abs": _nonnegative(raw_cap),
                "differential_amplitude_abs": _nonnegative(d_cap),
                "differential_velocity_abs": _nonnegative(velocity_cap),
                "energy_nonnegative": _nonnegative(energy_upper),
                "damping_work_magnitude": _nonnegative(damping_upper),
                "source_work": _nonnegative(Decimal(0)),
                "projection_roundtrip_abs": _nonnegative(projection_upper),
                "metric_projection_gain": [_outward(Decimal(1), Decimal(1)) for _ in rows],
                "workspace_peak_bytes": {"lower": str(workspace_peak), "upper": str(workspace_peak)},
                "workspace_byte_cap": cap,
                "work_closure_abs": _nonnegative(closure),
                "nonlinear_coefficient_abs": [_nonnegative(abs(value)) for value in kappa_values],
            },
            "positivity": {"metric_cell_area_positive": True, "d_coordinate_weight_positive": weight > 0, "rho_floor_positive": rho_floor > 0, "wave_speed_squared_nonnegative": all(value >= 0 for value in c_values), "damping_nonnegative": all(value >= 0 for value in gamma_values), "energy_terms_nonnegative": True, "source_admission": "only-empty-source" if source_budget == 0 else "profile-budgeted-source", "nonlinear_projection": "metric-adjoint-complete-frequency"},
            "derivation_formulae": {"laplacian": "lambda(k)=-(kx^2+ky^2), k_axis=2*pi*n_axis/L_axis", "spectral_maximum": "max over every signed W2 FFT bin on each active (Ny,Nx) sheet", "frequency": "Omega_D,s(k)=sqrt(omega_D,s^2+c_D,s^2*(kx^2+ky^2))", "damped_branches": "exact underdamped/critical/overdamped analytic 2x2 matrix, evaluated once per spectral half-stage", "half_amplification": "metric-normalized Frobenius enclosure of exp(A_D(k)*tau), tau=stage duration", "force_kick": "metric-normalized Frobenius enclosure with cubic-force Jacobian norm <=3*abs(kappa_D,s)*D_domain^2", "raw_admission": "amplitude_cap/product(stage_amplification)", "metric": "W_s=dx_s*dy_s*I and ||I_s R_s||_(W_s)=1", "projection": "complete-signed-frequency injection/restriction with metric-adjoint projection", "energy": "sum_s w_D*N_s*dx_s*dy_s*(|V_D|^2+(c_D,s^2*k2_max,s+omega_D,s^2)*|D|^2+abs(kappa_D,s)*|D|^4/2)/2", "workspace": "state bytes plus active and oversampled complex workspaces, bounded by semantic workspace.byte_cap", "rounding": "outward-nextafter-f64 after Decimal derivation"},
            "consumed_parameter_check": {"phi": _tag_dec(phi), "c_D_m_per_s": [_tag_dec(value) for value in c_values], "omega_D_rad_per_s": [_tag_dec(value) for value in omega_values], "gamma_D_per_s": [_tag_dec(value) for value in gamma_values], "kappa_D": [_tag_dec(value) for value in kappa_values], "max_k2_m2": _tag_dec(max_k2), "branches": [sorted(values) for values in per_scale_branches]},
        }


def _verify_source(root: Path, index: Mapping[str, Any]) -> dict[str, Any]:
    identity = _load(root / "run-spec" / "source-identity.json")
    if set(identity) != {"schema", "sources", "source_identity_sha256"} or identity["schema"] != SOURCE_IDENTITY_SCHEMA:
        _fail("W3N source identity schema mismatch")
    core = {"schema": identity["schema"], "sources": identity["sources"]}
    if identity["source_identity_sha256"] != _hash(core, SOURCE_IDENTITY_SCHEMA) or index["source_identity_sha256"] != identity["source_identity_sha256"]:
        _fail("W3N source identity hash mismatch")
    if [row.get("path") for row in identity["sources"]] != list(SOURCE_PATHS):
        _fail("W3N source inventory mismatch")
    for row in identity["sources"]:
        relative = row["path"]
        live = (ROOT / relative).read_bytes()
        archived = (root / "sources" / relative).read_bytes()
        if live != archived or row.get("bytes") != len(live) or row.get("sha256") != _sha(live):
            _fail(f"W3N source snapshot is stale: {relative}")
    return identity


def _verify_objects(root: Path, index: Mapping[str, Any]) -> None:
    expected = {row["path"]: (row["bytes"], row["sha256"]) for row in index["objects"]}
    actual_paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "index.json")
    if sorted(expected) != actual_paths:
        _fail("W3N object inventory mismatch")
    for relative, (size, digest) in expected.items():
        raw = (root / relative).read_bytes()
        if len(raw) != size or _sha(raw) != digest:
            _fail(f"W3N object hash mismatch: {relative}")


def _raw_hash(raw: bytes, dtype: str, shape: Sequence[int]) -> str:
    if dtype != "float64":
        _fail("sealed raw identity dtype mismatch")
    domain = RAW_DOMAIN.encode("utf-8")
    dtype_bytes = b"float64"
    digest = hashlib.sha256()
    digest.update(len(domain).to_bytes(8, "big"))
    digest.update(domain)
    digest.update(len(dtype_bytes).to_bytes(8, "big"))
    digest.update(dtype_bytes)
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        digest.update(struct.pack(">Q", int(dimension)))
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _guard_receipt(certificate: Mapping[str, Any], extension: Mapping[str, Any], raw: bytes, *, dtype: Any, backend: Any, source: Any) -> dict[str, Any]:
    contract = certificate["online_guard_contract"]
    layout = contract["raw_layout"]
    prefix = [int(value) for value in layout["shape_prefix"]]
    batch_limit = int(layout["batch_limit"])
    stride = math.prod(prefix)
    layout_valid = len(raw) % 8 == 0 and stride > 0 and (len(raw) // 8) % stride == 0
    batch = (len(raw) // 8) // stride if layout_valid else 0
    layout_valid = layout_valid and 1 <= batch <= batch_limit
    shape = [*prefix, batch]
    maximum = 0.0
    finite = layout_valid
    if layout_valid:
        for (value,) in struct.iter_unpack("<d", raw):
            if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
                finite = False
                maximum = math.inf
                break
            maximum = max(maximum, abs(value))
    component_count = int(layout["component_count"])
    mode_count = int(layout["mode_count"])
    active_sites = [int(row[0]) * int(row[1]) for row in contract["active_shapes_yx"]]
    tails_zero = layout_valid
    if layout_valid:
        scales, width = prefix
        for scale in range(scales):
            for component in range(component_count):
                for mode in range(active_sites[scale], mode_count):
                    for lane in range(batch):
                        offset = ((scale * width + component * mode_count + mode) * batch + lane) * 8
                        if raw[offset:offset + 8] != b"\x00" * 8:
                            tails_zero = False
                            break
                    if not tails_zero:
                        break
                if not tails_zero:
                    break
            if not tails_zero:
                break
    observed_dtype = layout["dtype"] if dtype is None else dtype
    observed_backend = layout["device"] if backend is None else backend
    source_bytes = 0 if source is None else len(_bytes(source))
    threshold = _f64(contract["raw_component_admission_abs"], name="guard threshold")
    accepted = observed_dtype == contract["dtype"] and observed_backend == contract["backend"] and source_bytes <= int(contract["source_byte_budget"]) and layout_valid and finite and tails_zero and maximum <= threshold
    if observed_dtype != contract["dtype"]:
        reason = "dtype-mismatch"
    elif observed_backend != contract["backend"]:
        reason = "backend-mismatch"
    elif source_bytes > int(contract["source_byte_budget"]):
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
        "schema": GUARD_RECEIPT_SCHEMA,
        "certificate_sha256": certificate["self_sha256"],
        "guard_contract_sha256": _hash(contract, GUARD_SCHEMA),
        "raw_state_sha256": _raw_hash(raw, contract["dtype"], shape),
        "raw_state_byte_count": len(raw),
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
        "source_byte_budget": int(contract["source_byte_budget"]),
        "workspace_byte_cap": int(contract["workspace_byte_cap"]),
        "raw_component_max_abs": _tag(maximum if math.isfinite(maximum) else float.fromhex("0x1.fffffffffffffp+1023")),
        "raw_component_admission_abs": contract["raw_component_admission_abs"],
        "stage_schedule_sha256": contract["stage_schedule_sha256"],
        "rounding_budget_sha256": _hash(certificate["offline_derivation"]["enclosures"]["work_closure_abs"], DERIVATION_SCHEMA),
        "decision": "ACCEPT" if accepted else "REJECT",
        "reason": reason,
        "mutation_permitted": accepted,
    }
    receipt["self_sha256"] = _hash(receipt, GUARD_DOMAIN)
    return receipt


def verify_artifact(path: str | Path) -> dict[str, Any]:
    root = Path(path).resolve()
    index = _load(root / "index.json")
    if index.get("schema") != INDEX_SCHEMA or index.get("status") != "PASS_W3N_G3N":
        _fail("W3N index header mismatch")
    without_self = {key: value for key, value in index.items() if key != "self_sha256"}
    if index.get("self_sha256") != _hash(without_self, INDEX_SCHEMA):
        _fail("W3N index self hash mismatch")
    index_core = {key: value for key, value in index.items() if key not in {"run_id", "self_sha256"}}
    run_id = _hash(index_core, ARTIFACT_DOMAIN)
    if index.get("run_id") != run_id or (root.name != run_id and not root.name.startswith(".w3n-")):
        _fail("W3N run id mismatch")
    _verify_objects(root, index)
    _verify_source(root, index)

    parents = index["parents"]
    w1_identity = parents["w1"]
    w1_path = W1_ROOT / w1_identity["run_id"]
    if _sha((w1_path / "index.json").read_bytes()) != w1_identity["index_sha256"]:
        _fail("W3N W1 parent index identity mismatch")
    from verify_cassi_qi_flow import verify_g1_identity

    w1_receipt = verify_g1_identity(w1_path)
    if w1_receipt["profile_sha256"] != w1_identity["profile_sha256"] or w1_receipt["contract_root_sha256"] != w1_identity["contract_root_sha256"]:
        _fail("W3N W1 parent receipt mismatch")

    w3_identity = parents["w3"]
    w3_path = W3_ROOT / w3_identity["run_id"]
    if _sha((w3_path / "index.json").read_bytes()) != w3_identity["index_sha256"]:
        _fail("W3N W3 parent index identity mismatch")
    from verify_cassi_qi_transport import verify_artifact as verify_w3_artifact

    w3_receipt = verify_w3_artifact(w3_path)
    if w3_receipt.get("status") != "PASS_W3_G3":
        _fail("W3N accepted W3 parent is not independently valid")
    w3_index = _load(w3_path / "index.json")
    for field in ("profile_sha256", "contract_root_sha256", "semantic_sha256", "stage_schedule_sha256", "source_identity_sha256", "parent_w2_run_id", "parent_w2_profile_sha256", "parent_w2_contract_root_sha256"):
        if w3_identity.get(field) != w3_index.get(field):
            _fail(f"W3N W3 identity field mismatch: {field}")
    w2_path = W2_ROOT / w3_identity["parent_w2_run_id"]
    from verify_cassi_qi_geometry import verify_artifact as verify_w2_artifact

    if verify_w2_artifact(w2_path).get("status") != "PASS_W2_G2":
        _fail("W3N accepted W2 parent is not independently valid")

    w2 = _load(w2_path / "run-spec" / "w2-profile.json")
    w3 = _load(w3_path / "run-spec" / "w3-profile.json")
    schedule = _load(w3_path / "run-spec" / "w3-stage-schedule.json")
    derivation = _derive(w2, w3, schedule)
    certificate = _load(root / "certificate" / "certificate-root.json")
    extension = _load(root / "certificate" / "extension-0001.json")
    registry = _load(root / "certificate" / "schema-registry-extension.json")
    accepted_w3 = _load(root / "run-spec" / "accepted-w3.json")
    accepted_w1 = _load(root / "run-spec" / "accepted-w1.json")
    if accepted_w3 != w3_identity or accepted_w1 != w1_identity:
        _fail("W3N accepted parent records are not index-exact")
    consumed = [
        {"name": "w2_contract_root", "sha256": w2["contract_root_sha256"]},
        {"name": "w2_geometry_profile", "sha256": w2["profile_sha256"]},
        {"name": "w2_geometry_contract", "sha256": w2["geometry_contract_sha256"]},
        {"name": "w2_operator_semantic", "sha256": w2["operator_semantic_sha256"]},
        {"name": "w3_contract_root", "sha256": w3["contract_root_sha256"]},
        {"name": "w3_transport_profile", "sha256": w3["profile_sha256"]},
        {"name": "w3_transport_semantic", "sha256": w3["semantic_sha256"]},
        {"name": "w3_stage_schedule", "sha256": derivation["inputs"]["w3_stage_schedule_sha256"]},
    ]
    chain_id = _hash({"w2_parent": w3["parent_w2"], "consumed": consumed, "accepted_w3_artifact_identity": w3_identity}, CERTIFICATE_DOMAIN)
    layout = derivation["inputs"]["state_layout"]
    guard = {"schema": GUARD_SCHEMA, "dtype": layout["dtype"], "backend": layout["device"], "raw_layout": layout, "active_shapes_yx": derivation["inputs"]["active_shapes_yx"], "raw_component_admission_abs": derivation["enclosures"]["raw_component_admission_abs"]["upper"], "source_byte_budget": derivation["inputs"]["source_byte_budget"], "workspace_byte_cap": derivation["inputs"]["workspace_byte_cap"], "stage_schedule_sha256": derivation["inputs"]["w3_stage_schedule_sha256"], "reject_before_mutation": True, "no_interval_widening": True, "no_clipping": True, "no_substitute_derivation": True}
    expected_root = {"schema": CERTIFICATE_SCHEMA, "certificate_chain_id": chain_id, "chain_ordinal": 0, "parent_certificate_sha256": None, "profile_sha256": w3["profile_sha256"], "contract_root_sha256": w3["contract_root_sha256"], "transport_semantic_sha256": w3["semantic_sha256"], "operator_semantic_sha256": w2["operator_semantic_sha256"], "execution_schedule_sha256": derivation["inputs"]["w3_stage_schedule_sha256"], "w2_parent": w3["parent_w2"], "accepted_w3_artifact_identity": w3_identity, "consumed_semantic_subhashes": consumed, "offline_derivation": derivation, "online_guard_contract": guard, "complete_section_inventory": [], "chain_status": "provisional"}
    expected_root["self_sha256"] = _hash(expected_root, CERTIFICATE_DOMAIN)
    if certificate != expected_root:
        _fail("W3N numerical certificate does not match the independent periodic-FFT2 derivation")
    section = {"schema": SECTION_SCHEMA, "section_id": "intrinsic-w3-numerics", "owning_package": "W3N", "gate": "G3N", "required": True, "ordinal": 1, "profile_sha256": w3["profile_sha256"], "contract_root_sha256": w3["contract_root_sha256"], "transport_semantic_sha256": w3["semantic_sha256"], "operator_semantic_sha256": w2["operator_semantic_sha256"], "execution_schedule_sha256": derivation["inputs"]["w3_stage_schedule_sha256"], "offline_derivation_sha256": _hash(derivation, DERIVATION_SCHEMA), "online_guard_sha256": _hash(guard, GUARD_SCHEMA)}
    section["self_sha256"] = _hash(section, SECTION_SCHEMA)
    expected_extension = {"schema": EXTENSION_SCHEMA, "certificate_chain_id": chain_id, "chain_ordinal": 1, "parent_certificate_sha256": certificate["self_sha256"], "parent_section_inventory": [], "owning_package": "W3N", "gate": "G3N", "consumed_semantic_subhashes": consumed, "accepted_w3_artifact_identity": w3_identity, "added_section": section, "complete_section_inventory": [section], "chain_status": "final"}
    expected_extension["final_certificate_identity_sha256"] = _hash(expected_extension, EXTENSION_DOMAIN)
    expected_extension["self_sha256"] = _hash(expected_extension, EXTENSION_DOMAIN)
    if extension != expected_extension:
        _fail("W3N certificate extension mismatch")
    registry_core = {"schema": REGISTRY_SCHEMA, "parent_registry_sha256": w1_identity["schema_registry_sha256"], "parent_w1_run_id": w1_identity["run_id"], "entries": sorted([
        {"schema": CERTIFICATE_SCHEMA, "max_bytes": 262144, "lifecycle": "artifact", "semantic_parents": ["state_contract_sha256", "backend_capacity_sha256"]},
        {"schema": EXTENSION_SCHEMA, "max_bytes": 131072, "lifecycle": "artifact", "semantic_parents": ["state_contract_sha256", "backend_capacity_sha256"]},
        {"schema": GUARD_RECEIPT_SCHEMA, "max_bytes": 32768, "lifecycle": "receipt", "semantic_parents": ["state_contract_sha256", "backend_capacity_sha256"]},
    ], key=lambda row: row["schema"])}
    expected_registry = {**registry_core, "self_sha256": _hash(registry_core, REGISTRY_DOMAIN)}
    if registry != expected_registry:
        _fail("W3N schema registry extension mismatch")

    replay = _load(root / "gates" / "g03n-numerical-certificate" / "guard-replay.json")
    replay_core = {key: value for key, value in replay.items() if key != "self_sha256"}
    if replay.get("schema") != GUARD_REPLAY_SCHEMA or replay.get("self_sha256") != _hash(replay_core, GUARD_REPLAY_SCHEMA):
        _fail("W3N guard replay identity mismatch")
    seen: set[str] = set()
    for row in replay["cases"]:
        case_id = row["id"]
        if case_id in seen:
            _fail("duplicate W3N guard case")
        seen.add(case_id)
        raw = (root / row["raw_path"]).read_bytes()
        if len(raw) != row["raw_bytes"] or _sha(raw) != row["raw_sha256"]:
            _fail(f"W3N raw fixture mismatch: {case_id}")
        receipt = _load(root / row["receipt_path"])
        expected_receipt = _guard_receipt(certificate, extension, raw, dtype=row["dtype"], backend=row["backend"], source=row["source"])
        if receipt != expected_receipt or receipt["self_sha256"] != row["receipt_sha256"] or receipt["decision"] != row["expected_decision"] or receipt["reason"] != row["expected_reason"]:
            _fail(f"W3N guard replay mismatch: {case_id}")
    required_cases = {"accepted", "exact-boundary", "just-above-boundary", "dtype-mismatch", "backend-mismatch", "nonempty-source", "nonfinite", "negative-zero", "raw-byte-mutation", "malformed-layout", "batch-limit"}
    if seen != required_cases:
        _fail("W3N guard replay case inventory mismatch")

    controls = _load(root / "gates" / "g03n-numerical-certificate" / "controls.json")
    controls_core = {key: value for key, value in controls.items() if key != "self_sha256"}
    if controls.get("schema") != CONTROLS_SCHEMA or controls.get("status") != "PASS" or controls.get("self_sha256") != _hash(controls_core, CONTROLS_SCHEMA) or any(value is False for key, value in controls_core.items() if key not in {"schema", "status"}):
        _fail("W3N control receipt mismatch")
    candidate = _load(root / "gates" / "g03n-numerical-certificate" / "certificate.json")
    candidate_core = {key: value for key, value in candidate.items() if key != "self_sha256"}
    if candidate.get("schema") != CANDIDATE_SCHEMA or candidate.get("status") != "PASS_W3N_G3N" or candidate.get("self_sha256") != _hash(candidate_core, CANDIDATE_SCHEMA):
        _fail("W3N candidate receipt mismatch")
    status = _load(root / "gates" / "g03n-numerical-certificate" / "status.json")
    if status.get("status") != "PASS" or status.get("gate") != "G3N" or status.get("certificate_sha256") != certificate["self_sha256"] or status.get("candidate_sha256") != candidate["self_sha256"]:
        _fail("W3N status receipt mismatch")
    for field, expected in (("profile_sha256", w3["profile_sha256"]), ("contract_root_sha256", w3["contract_root_sha256"]), ("transport_semantic_sha256", w3["semantic_sha256"]), ("execution_schedule_sha256", derivation["inputs"]["w3_stage_schedule_sha256"]), ("numerical_certificate_sha256", certificate["self_sha256"]), ("certificate_extension_sha256", extension["self_sha256"]), ("registry_extension_sha256", registry["self_sha256"]), ("candidate_sha256", candidate["self_sha256"])):
        if index.get(field) != expected:
            _fail(f"W3N index linkage mismatch: {field}")
    return {"status": "PASS_W3N_G3N", "run_id": run_id, "profile_sha256": w3["profile_sha256"], "contract_root_sha256": w3["contract_root_sha256"], "transport_semantic_sha256": w3["semantic_sha256"], "numerical_certificate_sha256": certificate["self_sha256"], "final_certificate_identity_sha256": extension["final_certificate_identity_sha256"], "source_identity_sha256": index["source_identity_sha256"], "guard_case_count": len(seen)}


def verify(path: str | Path) -> dict[str, Any]:
    return verify_artifact(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(verify_artifact(args.artifact), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
