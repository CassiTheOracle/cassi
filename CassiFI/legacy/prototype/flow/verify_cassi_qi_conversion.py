"""Independent verifier for the source-exact W5 centered frozen-Q artifact.

Only stdlib is used here.  In particular this module never imports the W5
runtime: hashes, raw-state layout, the frozen-Q map, EMA, ancestry, and gate
receipts are checked from the sealed artifact itself.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent

INDEX_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w5-frozen-q-artifact.v1"
RAW_DOMAIN = b"cassi.qi-flow-w5-raw-state.v1"
PROFILE_DOMAIN = "cassi.qi-flow-conversion-profile.v1"
ROOT_DOMAIN = "cassi.qi-flow-w5-conversion-root.v1"
LAW_DOMAIN = "cassi.qi-flow-frozen-q-map.v1"
RECEIPT_DOMAIN = "cassi.qi-flow-w5-conversion-receipt.v1"
INTEGRATED_DOMAIN = "cassi.qi-flow-w5-integrated-receipt.v1"
CONTROL_SCHEMA = "cassi.qi-flow-w5-conversion-control.v1"
INTEGRATED_SCHEMA = "cassi.qi-flow-w5-integrated-control.v1"
CANDIDATE_SCHEMA = "cassi.qi-flow-w5-conversion-candidate.v1"
STATUS_SCHEMA = "cassi.qi-flow-g5-status.v1"
MEASUREMENTS_SCHEMA = "cassi.qi-flow-w5-conversion-measurements.v1"
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w5-conversion-source-identity.v1"
W4R_INDEX_SCHEMA = "cassi.qi-flow-w4r-retention-core-run-index.v1"
W4R_ARTIFACT_DOMAIN = "cassi.qi-flow-w4r-retention-core"
PARENT_VERIFICATION_SCHEMA = "cassi.qi-flow-parent-verification.v1"
PARENT_VERIFIER_RECEIPTS_SCHEMA = "cassi.qi-flow-parent-verifier-receipts.v1"

SOURCE_PATHS = (
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

DIRECT_CONTROL_IDS = (
    "balanced",
    "matched-energy-positive-imbalance",
    "matched-energy-negative-imbalance",
    "yang-heavy",
    "yin-heavy",
    "empty",
    "near-capacity",
    "heterogeneous",
    "multiscale",
    "lambda-off",
    "lambda-and-ema-off",
    "duplicate-invocation",
    "stale-ema",
    "mis-remapped-ema",
    "positive-work-reject",
    "negative-work-dissipative",
    "numerical-zero-work",
    "source-ambiguous-work",
)
INTEGRATED_LABELS = (
    "integrated-replay-a",
    "integrated-replay-b",
    "integrated-conversion-term-off",
)
INTEGRATED_STAGES = (
    "w3n_guarded_transport",
    "w4_corrected_carrier",
    "w4r_hamiltonian_topology",
    "w5_conversion",
)
PHASE_RULE = "own-phase; empty-target-inherits-other-sector; double-empty-remains-zero.v1"


class VerificationError(ValueError):
    """Raised for every malformed, stale, or semantically invalid artifact."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        require(not any(0xD800 <= ord(char) <= 0xDFFF for char in key), "surrogate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise VerificationError(f"nonfinite JSON constant: {value}")


def f64_tag(value: float) -> str:
    require(math.isfinite(value), "nonfinite expected f64")
    require(not (value == 0.0 and math.copysign(1.0, value) < 0.0), "negative expected zero")
    return "f64:" + struct.pack(">d", value).hex()


def f64(value: Any) -> float:
    require(isinstance(value, str) and value.startswith("f64:") and len(value) == 20, "canonical f64 required")
    try:
        result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    except (TypeError, ValueError, struct.error) as exc:
        raise VerificationError("malformed f64 tag") from exc
    require(math.isfinite(result), "nonfinite f64")
    require(not (result == 0.0 and math.copysign(1.0, result) < 0.0), "negative f64 zero")
    return result


def number(value: Any) -> float:
    if isinstance(value, str) and value.startswith("f64:"):
        return f64(value)
    require(isinstance(value, (int, float)) and not isinstance(value, bool), "numeric value required")
    result = float(value)
    require(math.isfinite(result), "finite numeric value required")
    return result


def validate(value: Any) -> None:
    if value is None or isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return
    if isinstance(value, float):
        raise VerificationError("decimal JSON scalar is not canonical")
    if isinstance(value, str):
        require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), "surrogate JSON string")
        if value.startswith(("f32:", "f64:")):
            require(value.startswith("f64:"), "unexpected f32 scalar")
            f64(value)
        return
    if isinstance(value, list):
        for item in value:
            validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str), "non-string JSON key")
            validate(key)
            validate(item)
        return
    raise VerificationError(f"unsupported canonical value: {type(value).__name__}")


def canonical(value: Any) -> bytes:
    validate(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8")
    payload = canonical(value)
    return hashlib.sha256(len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload).hexdigest()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def raw_hash(raw: bytes) -> str:
    return sha(len(RAW_DOMAIN).to_bytes(8, "big") + RAW_DOMAIN + len(raw).to_bytes(8, "big") + raw)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8", "strict"), object_pairs_hook=_pairs, parse_constant=_constant)
    except VerificationError:
        raise
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid canonical JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"canonical object required: {path}")
    validate(value)
    return value


def self_hash(value: Mapping[str, Any], domain: str, name: str = "self_sha256") -> None:
    body = dict(value)
    claim = body.pop(name, None)
    require(isinstance(claim, str) and claim == digest(body, domain), f"bad {name} for {domain}")


def close(actual: float, expected: float, message: str, *, rel: float = 2.0e-12, absolute: float = 2.0e-12) -> None:
    require(math.isfinite(actual) and math.isfinite(expected), f"{message}: nonfinite")
    require(math.isclose(actual, expected, rel_tol=rel, abs_tol=absolute), f"{message}: {actual!r} != {expected!r}")


def _reject_w5v(value: Any, where: str = "artifact") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if "w5v_forward_domain_certificate" in key:
                require(item is None, f"{where}.{key}: W5V certificate must be absent/null")
            _reject_w5v(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_w5v(item, f"{where}[{index}]")


def _read_bytes(path: Path, where: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"missing {where}: {path}") from exc


def _layout(root_obj: Mapping[str, Any]) -> tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float]:
    layout = root_obj.get("state_layout")
    require(isinstance(layout, dict), "state_layout missing")
    require(layout.get("component_count") == 9, "frozen-Q requires nine state components")
    require(layout.get("dtype") == "float64", "raw state dtype")
    require(layout.get("byte_order") == "little", "raw state byte order")
    require(layout.get("layout_id") == "cassi.qi-flow-state-layout.v3", "raw state layout id")
    require(
        layout.get("component_order")
        == ["Y_re", "Y_im", "I_re", "I_im", "VY_re", "VY_im", "VI_re", "VI_im", "epsilon2_ema"],
        "raw state component order",
    )
    scales, modes, batch_limit = layout.get("scale_count"), layout.get("mode_count"), layout.get("batch_limit")
    require(isinstance(scales, int) and scales > 0, "state scale_count")
    require(isinstance(modes, int) and modes > 0, "state mode_count")
    require(isinstance(batch_limit, int) and batch_limit > 0, "state batch_limit")
    shape = layout.get("shape")
    require(isinstance(shape, list) and len(shape) == 3 and shape[0] == scales and shape[1] == 9 * modes, "state shape")
    require(shape[2] is None or (isinstance(shape[2], int) and shape[2] > 0), "state batch shape")
    active_shapes = layout.get("active_shapes")
    active_counts = layout.get("active_site_counts")
    require(isinstance(active_shapes, list) and len(active_shapes) == scales, "state active shapes")
    require(isinstance(active_counts, list) and len(active_counts) == scales, "state active site counts")
    parsed_shapes: list[tuple[int, int]] = []
    parsed_counts: list[int] = []
    for index, (item, count) in enumerate(zip(active_shapes, active_counts, strict=True)):
        require(isinstance(item, list) and len(item) == 2, f"state active shape[{index}]")
        ny, nx = item
        require(isinstance(ny, int) and isinstance(nx, int) and ny > 0 and nx > 0, f"state active shape[{index}]")
        require(isinstance(count, int) and count == ny * nx and 0 < count <= modes, f"state active count[{index}]")
        parsed_shapes.append((ny, nx))
        parsed_counts.append(count)
    bounds = layout.get("state_bounds")
    require(isinstance(bounds, dict), "state bounds")
    tail = number(bounds.get("inactive_tail_value"))
    require(tail == 0.0, "inactive raw tail must be exact zero")
    return scales, modes, batch_limit, int(shape[2] or 0), tuple(parsed_shapes), tuple(parsed_counts), tail


def _decode(raw: bytes, layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float]) -> tuple[list[float], int]:
    scales, modes, batch_limit, declared_batch, _, active_counts, tail = layout
    width = scales * 9 * modes
    require(len(raw) % (8 * width) == 0, "raw state byte length/layout")
    batch = len(raw) // (8 * width)
    require(0 < batch <= batch_limit, "raw batch outside declared limit")
    require(declared_batch in (0, batch), "raw batch does not match state shape")
    values = list(struct.unpack("<" + "d" * (width * batch), raw))
    require(all(math.isfinite(value) for value in values), "nonfinite raw state")
    for scale, active in enumerate(active_counts):
        for component in range(9):
            for mode in range(active, modes):
                for lane in range(batch):
                    value = values[_idx(scale, component, mode, lane, modes, batch, scales)]
                    close(value, tail, f"inactive tail scale={scale} component={component} mode={mode}", rel=0.0, absolute=0.0)
    return values, batch


def _idx(scale: int, component: int, mode: int, batch: int, modes: int, batches: int, scales: int) -> int:
    require(0 <= scale < scales and 0 <= component < 9 and 0 <= mode < modes and 0 <= batch < batches, "raw state index outside layout")
    return ((scale * 9 + component) * modes + mode) * batches + batch


def _lane(values: list[float], scale: int, component: int, modes: int, batches: int, scales: int) -> tuple[float, ...]:
    return tuple(values[_idx(scale, component, mode, batch, modes, batches, scales)] for mode in range(modes) for batch in range(batches))


def _duration_records(profile: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    clock = profile.get("clock")
    require(isinstance(clock, dict), "conversion clock")
    rows = clock.get("runtime_exact_rationals")
    require(isinstance(rows, list) and rows, "registered physical durations")
    result: list[tuple[int, int]] = []
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"numerator", "denominator"}, "duration rational row")
        numerator, denominator = row["numerator"], row["denominator"]
        require(isinstance(numerator, int) and isinstance(denominator, int) and numerator > 0 and denominator > 0, "duration rational")
        require(math.gcd(numerator, denominator) == 1, "duration rational must be reduced")
        require(1.0 / 1000.0 <= numerator / denominator <= 1.0 / 100.0, "duration outside [1/1000,1/100]")
        result.append((numerator, denominator))
    require(len(set(result)) == len(result), "duplicate registered duration")
    h_min, h_max = clock.get("h_min"), clock.get("h_max")

    require(isinstance(h_min, dict) and isinstance(h_max, dict), "clock bounds")
    require((h_min.get("numerator"), h_min.get("denominator")) in result and (h_max.get("numerator"), h_max.get("denominator")) in result, "clock bounds not registered")
    require(clock.get("runtime_membership") == "reduced-positive-rational-closed-interval.v1", "clock membership")
    return tuple(result)
def _work_uncertainty(profile: Mapping[str, Any]) -> float:
    return max(
        number(profile.get("energy_uncertainty", profile.get("margins", {}).get("U_conversion"))),
        number(profile.get("work_tolerance", profile.get("margins", {}).get("U_conversion"))),
    )


def _parameters(profile: Mapping[str, Any]) -> tuple[float, float, float, float]:
    return (
        number(profile.get("phi")),
        number(profile.get("lambda_rate")),
        number(profile.get("rho_ref")),
        number(profile.get("epsilon_memory_time_s")),
    )

def _support_limits(profile: Mapping[str, Any]) -> tuple[float, float, float]:
    support = profile.get("support")
    require(
        isinstance(support, dict)
        and isinstance(support.get("D_conv"), dict)
        and isinstance(support.get("A_accepted"), dict),
        "conversion support",
    )
    domain, accepted = support["D_conv"], support["A_accepted"]
    density = domain.get("position_density")
    if isinstance(density, dict):
        rho_max = number(density.get("EY_plus_EI_max"))
    else:
        rho_max = number(accepted.get("density_sum_at_most"))
    ema = domain.get("epsilon2_ema")
    if isinstance(ema, dict):
        ema_max = number(ema.get("max"))
    else:
        require(isinstance(ema, list) and len(ema) == 2, "conversion EMA bounds")
        ema_max = number(ema[1])
    density_tol = number(accepted.get("density_conservation_abs"))
    return rho_max, ema_max, density_tol


def _duration_value(value: Any, registered: tuple[tuple[int, int], ...]) -> tuple[float, tuple[int, int]]:
    if isinstance(value, dict):
        numerator, denominator = value.get("numerator"), value.get("denominator")
        require(isinstance(numerator, int) and isinstance(denominator, int) and numerator > 0 and denominator > 0 and math.gcd(numerator, denominator) == 1, "duration rational")
        require((numerator, denominator) in registered, "unregistered duration")
        return numerator / denominator, (numerator, denominator)
    result = number(value)
    pair = next(((n, d) for n, d in registered if result == n / d), None)
    require(pair is not None, "duration is not an exact registered rational")
    return result, pair




def _replay_map(raw: bytes, profile: Mapping[str, Any], root_obj: Mapping[str, Any], duration: float, *, lambda_rate: float | None = None, tau_override: float | None = None) -> dict[str, Any]:
    layout = _layout(root_obj)
    values, batches = _decode(raw, layout)
    scales, modes, _, _, _, active_counts, _ = layout
    mapped, final = list(values), list(values)
    phi, profile_rate, rho_ref, memory_time = _parameters(profile)
    rate = profile_rate if lambda_rate is None else lambda_rate
    rho_max, ema_max, density_tol = _support_limits(profile)
    require(rho_ref > 0.0 and phi > 0.0 and memory_time > 0.0 and rate >= 0.0, "invalid frozen-Q parameters")
    tau = -math.expm1(-duration / memory_time) if tau_override is None else tau_override
    require(0.0 <= tau <= 1.0 and math.isfinite(tau), "invalid physical-time EMA coefficient")
    sqrt_phi = math.sqrt(phi)
    rows: list[dict[str, Any]] = []
    phase_counts = {"yang-own-phase": 0, "yin-own-phase": 0, "empty-yang-inherits-yin": 0, "empty-yin-inherits-yang": 0, "double-empty": 0}
    for scale in range(scales):
        q_values: list[float] = []
        alpha_values: list[float] = []
        epsilon_values: list[float] = []
        transfers: list[float] = []
        density_pre = density_post = reconstructed = 0.0
        analytic_closure = reconstructed_closure = 0.0
        balanced_count = zero_count = 0
        row_phase_counts = {key: 0 for key in phase_counts}
        for mode in range(active_counts[scale]):
            for batch in range(batches):
                yr = values[_idx(scale, 0, mode, batch, modes, batches, scales)]
                yi = values[_idx(scale, 1, mode, batch, modes, batches, scales)]
                ir = values[_idx(scale, 2, mode, batch, modes, batches, scales)]
                ii = values[_idx(scale, 3, mode, batch, modes, batches, scales)]
                ema = values[_idx(scale, 8, mode, batch, modes, batches, scales)]
                yang_abs, yin_abs = math.hypot(yr, yi), math.hypot(ir, ii)
                ey, ei = yang_abs * yang_abs, yin_abs * yin_abs
                rho = ey + ei
                require(0.0 <= ema <= ema_max + density_tol and rho <= rho_max + density_tol, "raw fixture outside frozen support")
                epsilon = (yang_abs - sqrt_phi * yin_abs) * (yang_abs + sqrt_phi * yin_abs)
                rho_bar, ema_bar = rho / rho_ref, ema / (rho_ref * rho_ref)
                denominator = rho_bar * rho_bar + phi ** -2 + ema_bar
                require(denominator > 0.0, "frozen-Q denominator")
                q = rho_bar * rho_bar / denominator
                alpha = math.exp(-(1.0 + phi) * rate * (1.0 - q) * duration)
                transfer = epsilon * (1.0 - alpha) / (1.0 + phi)
                ey_next, ei_next = ey - transfer, ei + transfer
                require(ey_next >= 0.0 and ei_next >= 0.0 and ey_next + ei_next <= rho_max + density_tol, "closed-form conversion left support")
                if ey > 0.0:
                    factor = math.sqrt(ey_next / ey)
                    nyr, nyi = yr * factor, yi * factor
                elif ei > 0.0:
                    factor = math.sqrt(ey_next / ei)
                    nyr, nyi = ir * factor, ii * factor
                else:
                    nyr = nyi = 0.0
                if ei > 0.0:
                    factor = math.sqrt(ei_next / ei)
                    nir, nii = ir * factor, ii * factor
                elif ey > 0.0:
                    factor = math.sqrt(ei_next / ey)
                    nir, nii = yr * factor, yi * factor
                else:
                    nir = nii = 0.0
                for component, mapped_value in ((0, nyr), (1, nyi), (2, nir), (3, nii)):
                    mapped[_idx(scale, component, mode, batch, modes, batches, scales)] = mapped_value
                reconstructed_rho = nyr * nyr + nyi * nyi + nir * nir + nii * nii
                q_values.append(q)
                alpha_values.append(alpha)
                epsilon_values.append(epsilon)
                transfers.append(transfer)
                density_pre += rho
                density_post += ey_next + ei_next
                reconstructed += reconstructed_rho
                analytic_closure = max(analytic_closure, abs((ey_next + ei_next) - rho))
                reconstructed_closure = max(reconstructed_closure, abs(reconstructed_rho - rho))
                balanced_count += int(epsilon == 0.0)
                zero_count += int(ey == 0.0 and ei == 0.0)
                if ey > 0.0:
                    row_phase_counts["yang-own-phase"] += 1
                if ei > 0.0:
                    row_phase_counts["yin-own-phase"] += 1
                if ey == 0.0 and ei > 0.0:
                    row_phase_counts["empty-yang-inherits-yin"] += 1
                if ey > 0.0 and ei == 0.0:
                    row_phase_counts["empty-yin-inherits-yang"] += 1
                if ey == 0.0 and ei == 0.0:
                    row_phase_counts["double-empty"] += 1
        for key in phase_counts:
            phase_counts[key] += row_phase_counts[key]
        for index in range(len(mapped)):
            final[index] = mapped[index]
        for mode in range(active_counts[scale]):
            for batch in range(batches):
                yr = mapped[_idx(scale, 0, mode, batch, modes, batches, scales)]
                yi = mapped[_idx(scale, 1, mode, batch, modes, batches, scales)]
                ir = mapped[_idx(scale, 2, mode, batch, modes, batches, scales)]
                ii = mapped[_idx(scale, 3, mode, batch, modes, batches, scales)]
                old = values[_idx(scale, 8, mode, batch, modes, batches, scales)]
                yang_abs, yin_abs = math.hypot(yr, yi), math.hypot(ir, ii)
                epsilon_next = (yang_abs - sqrt_phi * yin_abs) * (yang_abs + sqrt_phi * yin_abs)
                next_ema = (1.0 - tau) * old + tau * epsilon_next * epsilon_next
                require(0.0 <= next_ema <= ema_max + density_tol, "closed-form EMA left support")
                final[_idx(scale, 8, mode, batch, modes, batches, scales)] = next_ema
        rows.append({
            "scale": scale,
            "q_min": min(q_values),
            "q_max": max(q_values),
            "alpha_min": min(alpha_values),
            "alpha_max": max(alpha_values),
            "epsilon_min": min(epsilon_values),
            "epsilon_max": max(epsilon_values),
            "transfer_min": min(transfers),
            "transfer_max": max(transfers),
            "transfer_l1": sum(abs(value) for value in transfers),
            "signed_progress_min": min((math.copysign(1.0, e) * t if e else 0.0) for e, t in zip(epsilon_values, transfers, strict=True)),
            "density_pre": density_pre,
            "density_post_analytic": density_post,
            "density_post_reconstructed": reconstructed,
            "density_map_closure_abs": analytic_closure,
            "density_closure_abs": reconstructed_closure,
            "balanced_count": balanced_count,
            "zero_count": zero_count,
            "phase_branches": row_phase_counts,
        })
    require(all(row["density_map_closure_abs"] <= density_tol for row in rows), "density conservation")
    return {"mapped": mapped, "final": final, "rows": rows, "tau": tau, "phase_counts": phase_counts, "layout": layout, "batch": batches}


def _check_values(actual: list[float], expected: list[float], where: str, *, absolute: float = 2.0e-12) -> None:
    require(len(actual) == len(expected), f"{where}: raw length")
    for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
        close(left, right, f"{where}[{index}]", absolute=absolute)


def _phase_velocity_check(pre: list[float], candidate: list[float], layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float], where: str) -> None:
    scales, modes, _, declared_batch, _, _, _ = layout
    batches = len(pre) // (scales * 9 * modes)
    require(declared_batch in (0, batches), f"{where}: batch layout")
    for scale in range(scales):
        for mode in range(modes):
            for batch in range(batches):
                yr, yi = pre[_idx(scale, 0, mode, batch, modes, batches, scales)], pre[_idx(scale, 1, mode, batch, modes, batches, scales)]
                ir, ii = pre[_idx(scale, 2, mode, batch, modes, batches, scales)], pre[_idx(scale, 3, mode, batch, modes, batches, scales)]
                nyr, nyi = candidate[_idx(scale, 0, mode, batch, modes, batches, scales)], candidate[_idx(scale, 1, mode, batch, modes, batches, scales)]
                nir, nii = candidate[_idx(scale, 2, mode, batch, modes, batches, scales)], candidate[_idx(scale, 3, mode, batch, modes, batches, scales)]
                ey, ei = yr * yr + yi * yi, ir * ir + ii * ii
                yref = (yr, yi) if ey > 0.0 else (ir, ii)
                iref = (ir, ii) if ei > 0.0 else (yr, yi)
                close(yref[0] * nyi - yref[1] * nyr, 0.0, f"{where} Yang phase", absolute=2.0e-11)
                close(iref[0] * nii - iref[1] * nir, 0.0, f"{where} Yin phase", absolute=2.0e-11)
                for component in (4, 5, 6, 7):
                    require(pre[_idx(scale, component, mode, batch, modes, batches, scales)] == candidate[_idx(scale, component, mode, batch, modes, batches, scales)], f"{where} velocity mutation")


def _identity_hash(value: Mapping[str, Any], claim_name: str, domain: str) -> str:
    body = dict(value)
    claim = body.pop(claim_name, None)
    require(isinstance(claim, str) and claim == digest(body, domain), f"bad {claim_name} for {domain}")
    return claim


def _upstream_profiles(root: Path) -> dict[str, dict[str, Any]]:
    value = read_json(root / "run-spec" / "upstream-profiles.json")
    require(value.get("schema") == "cassi.qi-flow-w5-upstream-profile-snapshot.v1", "upstream profile snapshot schema")
    expected = {"schema", "geometry", "transport", "carrier", "topology", "numerical_certificate", "self_sha256"}
    require(set(value) == expected, "upstream profile snapshot inventory")
    _identity_hash(value, "self_sha256", "cassi.qi-flow-w5-upstream-profile-snapshot.v1")
    profile_domains = {
        "geometry": "cassi.qi-flow-geometry-profile.w2.periodic-fft2.v1",
        "transport": "cassi.qi-flow-transport-profile.w3",
        "carrier": "cassi.qi-flow-w4-carrier-profile.v1",
        "topology": "cassi.qi-flow-w4r-topology-profile.v1",
    }
    root_domains = {
        "geometry": "cassi.qi-flow-contract-root.w2.periodic-fft2.v1",
        "transport": "cassi.qi-flow-contract-root.w3",
        "carrier": "cassi.qi-flow-w4-carrier-root.v1",
        "topology": "cassi.qi-flow-w4r-topology-root.v1",
    }
    result: dict[str, dict[str, Any]] = {}
    for kind in ("geometry", "transport", "carrier", "topology"):
        item = value.get(kind)
        require(isinstance(item, dict) and set(item) == {"payload", "root", "identity"}, f"upstream {kind} snapshot")
        payload, contract_root, identity = item["payload"], item["root"], item["identity"]
        require(isinstance(payload, dict) and isinstance(contract_root, dict) and isinstance(identity, dict), f"upstream {kind} objects")
        profile_claim = payload.get("profile_sha256")
        require(isinstance(profile_claim, str), f"upstream {kind} profile identity")
        _identity_hash(payload, "profile_sha256", profile_domains[kind])
        root_claim = contract_root.get("self_sha256")
        require(isinstance(root_claim, str), f"upstream {kind} root identity")
        _identity_hash(contract_root, "self_sha256", root_domains[kind])
        for name in ("profile_sha256", "root_sha256", "contract_root_sha256"):
            if name in identity:
                require(identity[name] in {profile_claim, root_claim, contract_root.get(name)}, f"upstream {kind} identity link")
        result[kind] = {"payload": payload, "root": contract_root, "identity": identity}
    certificate = value["numerical_certificate"]
    require(
        isinstance(certificate, dict)
        and set(certificate) == {"identity"}
        and isinstance(certificate["identity"], dict)
        and certificate["identity"]
        and all(
            str(key).lower().endswith("_sha256")
            and isinstance(item, str)
            and len(item) == 64
            and item == item.lower()
            and all(char in "0123456789abcdef" for char in item)
            for key, item in certificate["identity"].items()
        ),
        "upstream numerical certificate identity",
    )
    result["numerical_certificate"] = {"identity": certificate["identity"]}
    return result


def _sheet_rows(upstream: Mapping[str, Any], layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float]) -> tuple[dict[str, Any], ...]:
    scales, _, _, _, active_shapes, active_counts, _ = layout
    geometry = upstream["geometry"]["payload"]
    contract = geometry.get("geometry_contract")
    require(isinstance(contract, dict), "upstream geometry contract")
    rows = contract.get("per_scale_sheets")
    if not isinstance(rows, list):
        semantic = upstream["transport"]["payload"].get("semantic")
        rows = semantic.get("geometry", {}).get("per_scale") if isinstance(semantic, dict) else None
    require(isinstance(rows, list) and len(rows) == scales, "upstream geometry scale rows")
    result: list[dict[str, Any]] = []
    for scale, row in enumerate(rows):
        require(isinstance(row, dict), f"geometry scale row {scale}")
        shape = row.get("active_shape")
        if shape is None:
            rectangle = row.get("active_rectangle")
            shape = rectangle.get("shape_yx") if isinstance(rectangle, dict) else row.get("shape_yx")
        require(isinstance(shape, list) and len(shape) == 2 and tuple(shape) == active_shapes[scale], f"geometry shape {scale}")
        require(number(row.get("cell_area_m2", row.get("metric_cell_area"))) > 0.0, f"geometry cell area {scale}")
        spacing = row.get("spacing_m")
        extent = row.get("extent_m")
        if isinstance(spacing, dict):
            spacing = [spacing.get("dy"), spacing.get("dx")]
        if isinstance(extent, dict):
            extent = [extent.get("L_y"), extent.get("L_x")]
        require(isinstance(spacing, list) and len(spacing) == 2, f"geometry spacing {scale}")
        require(isinstance(extent, list) and len(extent) == 2, f"geometry extent {scale}")
        frequency_y = row.get("signed_frequency_y")
        frequency_x = row.get("signed_frequency_x")
        if frequency_y is None or frequency_x is None:
            frequencies = row.get("signed_frequency_bins")
            frequency_y = frequencies.get("y") if isinstance(frequencies, dict) else None
            frequency_x = frequencies.get("x") if isinstance(frequencies, dict) else None
        require(isinstance(frequency_y, list) and isinstance(frequency_x, list), f"geometry frequencies {scale}")
        require(len(frequency_y) == shape[0] and len(frequency_x) == shape[1], f"geometry frequency lengths {scale}")
        require(active_counts[scale] == shape[0] * shape[1], f"geometry active count {scale}")
        result.append({
            "shape": (int(shape[0]), int(shape[1])),
            "area": number(row.get("cell_area_m2", row.get("metric_cell_area"))),
            "extent": (number(extent[0]), number(extent[1])),
            "ky": tuple(number(item) for item in frequency_y),
            "kx": tuple(number(item) for item in frequency_x),
        })
    return tuple(result)


def _grid(values: list[float], scale: int, component: int, lane: int, layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float], batches: int) -> list[list[complex]]:
    scales, modes, _, _, shapes, _, _ = layout
    ny, nx = shapes[scale]
    return [
        [
            complex(
                values[_idx(scale, component, y * nx + x, lane, modes, batches, scales)],
                values[_idx(scale, component + 1, y * nx + x, lane, modes, batches, scales)],
            )
            for x in range(nx)
        ]
        for y in range(ny)
    ]


def _spectral_gradient(grid: list[list[complex]], sheet: Mapping[str, Any]) -> tuple[list[list[complex]], list[list[complex]]]:
    ny, nx = sheet["shape"]
    ly, lx = sheet["extent"]
    ky, kx = sheet["ky"], sheet["kx"]
    norm = math.sqrt(float(ny * nx))
    spectrum = [[0j for _ in range(nx)] for _ in range(ny)]
    for fy in range(ny):
        for fx in range(nx):
            total = 0j
            for y in range(ny):
                for x in range(nx):
                    phase = -2.0 * math.pi * (ky[fy] * y / ny + kx[fx] * x / nx)
                    total += grid[y][x] * complex(math.cos(phase), math.sin(phase))
            spectrum[fy][fx] = total / norm
    dx_grid = [[0j for _ in range(nx)] for _ in range(ny)]
    dy_grid = [[0j for _ in range(nx)] for _ in range(ny)]
    for y in range(ny):
        for x in range(nx):
            dx_value = dy_value = 0j
            for fy in range(ny):
                for fx in range(nx):
                    phase = 2.0 * math.pi * (ky[fy] * y / ny + kx[fx] * x / nx)
                    basis = complex(math.cos(phase), math.sin(phase)) / norm
                    dx_value += spectrum[fy][fx] * (1j * 2.0 * math.pi * kx[fx] / lx) * basis
                    dy_value += spectrum[fy][fx] * (1j * 2.0 * math.pi * ky[fy] / ly) * basis
            dx_grid[y][x], dy_grid[y][x] = dx_value, dy_value
    return dx_grid, dy_grid


def _energy_model(upstream: Mapping[str, Any], layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float]) -> dict[str, Any]:
    scales, _, _, _, _, _, _ = layout
    carrier = upstream["carrier"]["payload"]
    dynamics = carrier.get("dynamics")
    transform = carrier.get("d_c_transform")
    composition = carrier.get("composition")
    require(isinstance(dynamics, dict) and isinstance(transform, dict) and isinstance(composition, dict), "carrier energy model")
    phi = number(transform.get("phi"))
    w_d, w_c = 1.0 / (1.0 + phi * phi), 1.0 + phi * phi
    metric = transform.get("metric")
    require(isinstance(metric, dict) and metric.get("w_D") == "1/(1+phi^2)" and metric.get("w_C") == "1+phi^2", "carrier metric law")
    d_data, c_data = dynamics.get("D"), dynamics.get("C")
    require(isinstance(d_data, dict) and isinstance(c_data, dict), "carrier D/C dynamics")
    beta, epsilon_ref = composition.get("beta"), composition.get("epsilon_ref")
    require(isinstance(beta, list) and isinstance(epsilon_ref, list) and len(beta) == scales and len(epsilon_ref) == scales, "carrier composition scales")
    def arrays(data: Mapping[str, Any]) -> tuple[tuple[float, ...], ...]:
        result = []
        for name in ("c_m_per_s", "omega_rad_per_s", "gamma_per_s", "kappa"):
            values = data.get(name)
            require(isinstance(values, list) and len(values) == scales, f"carrier dynamics {name}")
            parsed = tuple(number(item) for item in values)
            require(all(item >= 0.0 for item in parsed), f"carrier dynamics {name} sign")
            result.append(parsed)
        return tuple(result)
    d_arrays, c_arrays = arrays(d_data), arrays(c_data)
    topology = upstream["topology"]["payload"]
    require(isinstance(topology, dict), "topology energy model")
    return {
        "phi": phi,
        "w_d": w_d,
        "w_c": w_c,
        "beta": tuple(number(item) for item in beta),
        "epsilon_ref": tuple(number(item) for item in epsilon_ref),
        "d": d_arrays,
        "c": c_arrays,
        "topology": topology,
    }


def _energy_from_raw(raw: bytes, root_obj: Mapping[str, Any], upstream: Mapping[str, Any]) -> dict[str, float]:
    layout = _layout(root_obj)
    values, batches = _decode(raw, layout)
    scales, modes, _, _, shapes, _, _ = layout
    sheets = _sheet_rows(upstream, layout)
    model = _energy_model(upstream, layout)
    carrier_total = kinetic_total = gradient_total = local_total = composition_total = topology_total = 0.0
    for scale in range(scales):
        ny, nx = shapes[scale]
        sheet = sheets[scale]
        for lane in range(batches):
            ey, ei = _grid(values, scale, 0, lane, layout, batches), _grid(values, scale, 2, lane, layout, batches)
            vy, vi = _grid(values, scale, 4, lane, layout, batches), _grid(values, scale, 6, lane, layout, batches)
            d = [[ey[y][x] - model["phi"] * ei[y][x] for x in range(nx)] for y in range(ny)]
            c = [[(model["phi"] * ey[y][x] + ei[y][x]) * model["w_d"] for x in range(nx)] for y in range(ny)]
            vd = [[vy[y][x] - model["phi"] * vi[y][x] for x in range(nx)] for y in range(ny)]
            vc = [[(model["phi"] * vy[y][x] + vi[y][x]) * model["w_d"] for x in range(nx)] for y in range(ny)]
            d_dx, d_dy = _spectral_gradient(d, sheet)
            c_dx, c_dy = _spectral_gradient(c, sheet)
            kinetic_lane = gradient_lane = local_lane = composition_lane = 0.0
            for y in range(ny):
                for x in range(nx):
                    d2, c2 = abs(d[y][x]) ** 2, abs(c[y][x]) ** 2
                    vd2, vc2 = abs(vd[y][x]) ** 2, abs(vc[y][x]) ** 2
                    d_grad = abs(d_dx[y][x]) ** 2 + abs(d_dy[y][x]) ** 2
                    c_grad = abs(c_dx[y][x]) ** 2 + abs(c_dy[y][x]) ** 2
                    kinetic_lane += model["w_d"] * 0.5 * vd2 + model["w_c"] * 0.5 * vc2
                    gradient_lane += model["w_d"] * 0.5 * model["d"][0][scale] ** 2 * d_grad + model["w_c"] * 0.5 * model["c"][0][scale] ** 2 * c_grad
                    local_lane += model["w_d"] * (0.5 * model["d"][1][scale] ** 2 * d2 + 0.25 * model["d"][3][scale] * d2 * d2)
                    local_lane += model["w_c"] * (0.5 * model["c"][1][scale] ** 2 * c2 + 0.25 * model["c"][3][scale] * c2 * c2)
                    epsilon = abs(ey[y][x]) ** 2 - model["phi"] * abs(ei[y][x]) ** 2
                    composition_lane += 0.5 * model["w_c"] * model["c"][1][scale] ** 2 * model["beta"][scale] * math.tanh(epsilon / model["epsilon_ref"][scale]) * c2
            area = sheet["area"]
            kinetic_total += kinetic_lane * area
            gradient_total += gradient_lane * area
            local_total += local_lane * area
            composition_total += composition_lane * area
            carrier_total += (kinetic_lane + gradient_lane + local_lane + composition_lane) * area
    topology = model["topology"]
    if topology.get("mode") == "topological-v1":
        slow = topology.get("slow_scale")
        require(isinstance(slow, int) and 0 <= slow < scales, "topology slow scale")
        ny, nx = shapes[slow]
        require(topology.get("active_shape_yx") == [ny, nx], "topology shape")
        rotation, potential = topology.get("weighted_rotation"), topology.get("potential")
        require(isinstance(rotation, dict) and isinstance(potential, dict), "topology potential model")
        a, b = number(rotation.get("a_topo")), number(rotation.get("b_topo"))
        E, lambda_ph = number(potential.get("E_topo")), number(potential.get("lambda_ph"))
        lambda_core = number(potential.get("lambda_core"))
        r_core, rho_ring = number(potential.get("r_core")), number(potential.get("rho_ring"))
        edges = topology.get("edge_registry")
        require(isinstance(edges, list) and edges, "topology edge registry")
        metric_diag = topology.get("metric_diagonal")
        metric_values = [sheet["area"]] * (ny * nx) if metric_diag is None else [number(item) for item in metric_diag]
        require(len(metric_values) == ny * nx and all(item > 0.0 for item in metric_values), "topology metric diagonal")
        for lane in range(batches):
            ey, ei = _grid(values, slow, 0, lane, layout, batches), _grid(values, slow, 2, lane, layout, batches)
            d = [[ey[y][x] - model["phi"] * ei[y][x] for x in range(nx)] for y in range(ny)]
            c = [[(model["phi"] * ey[y][x] + ei[y][x]) * model["w_d"] for x in range(nx)] for y in range(ny)]
            psi = [[a * math.sqrt(model["w_d"]) * d[y][x] + b * math.sqrt(model["w_c"]) * c[y][x] for x in range(nx)] for y in range(ny)]
            smooth = [[psi[y][x] / math.sqrt(abs(psi[y][x]) ** 2 + r_core * r_core) for x in range(nx)] for y in range(ny)]
            edge_sum = 0.0
            edge_weight = 0.0
            for row in edges:
                require(isinstance(row, dict), "topology edge row")
                source, target = row.get("source"), row.get("target")
                if isinstance(source, int):
                    sy, sx = divmod(source, nx)
                elif isinstance(source, list) and len(source) == 2:
                    sy, sx = int(source[0]), int(source[1])
                else:
                    raise VerificationError("topology edge source")
                if isinstance(target, int):
                    ty, tx = divmod(target, nx)
                elif isinstance(target, list) and len(target) == 2:
                    ty, tx = int(target[0]), int(target[1])
                else:
                    raise VerificationError("topology edge target")
                require(0 <= sy < ny and 0 <= sx < nx and 0 <= ty < ny and 0 <= tx < nx, "topology edge endpoint")
                weight = number(row.get("weight"))
                require(weight > 0.0, "topology edge weight")
                edge_sum += weight * (1.0 - (smooth[sy][sx].conjugate() * smooth[ty][tx]).real)
                edge_weight += weight
            phase_energy = edge_sum / edge_weight
            rho2 = rho_ring * rho_ring
            core_energy = sum(metric_values[y * nx + x] * (((abs(psi[y][x]) ** 2 - rho2) / (abs(psi[y][x]) ** 2 + rho2)) ** 2) for y in range(ny) for x in range(nx)) / sum(metric_values)
            topology_total += E * (lambda_ph * phase_energy + lambda_core * core_energy)
    total = carrier_total + topology_total
    return {
        "carrier": carrier_total,
        "topological": topology_total,
        "extra_conservative": 0.0,
        "link_energy": 0.0,
        "total": total,
        "kinetic": kinetic_total,
        "gradient": gradient_total,
        "local": local_total,
        "composition": composition_total,
    }


def _check_complete_energy(
    witness: Any,
    *,
    predecessor_raw: bytes,
    candidate_raw: bytes,
    root_obj: Mapping[str, Any],
    upstream: Mapping[str, Any],
    where: str,
) -> None:
    require(isinstance(witness, dict) and "error" not in witness and set(witness) == {"pre", "post"}, f"{where}: complete energy witness")
    for side, raw in (("pre", predecessor_raw), ("post", candidate_raw)):
        row = witness[side]
        require(isinstance(row, dict) and set(row) == {"kinetic", "gradient", "local", "composition", "link", "U_topo", "total", "per_scale"}, f"{where}.{side}: energy rows")
        expected = _energy_from_raw(raw, root_obj, upstream)
        for key, expected_key in (
            ("kinetic", "kinetic"),
            ("gradient", "gradient"),
            ("local", "local"),
            ("composition", "composition"),
            ("link", "link_energy"),
            ("U_topo", "topological"),
            ("total", "total"),
        ):
            close(number(row[key]), expected[expected_key], f"{where}.{side}.{key}", rel=2.0e-8, absolute=2.0e-8)
        close(number(row["total"]), expected["total"], f"{where}.{side}.total", rel=2.0e-8, absolute=2.0e-8)
        close(number(row["kinetic"]) + number(row["gradient"]) + number(row["local"]) + number(row["composition"]) + number(row["link"]), expected["carrier"], f"{where}.{side}.carrier closure", rel=2.0e-8, absolute=2.0e-8)
        scales, _, _, _, _, _, _ = _layout(root_obj)
        per_scale = row["per_scale"]
        require(isinstance(per_scale, list) and len(per_scale) == scales, f"{where}.{side}: per-scale energy rows")
        kinetic = gradient = local = 0.0
        for scale, item in enumerate(per_scale):
            require(isinstance(item, dict) and item.get("scale") == scale and set(item) == {"scale", "D", "C", "kinetic", "gradient", "local", "total"}, f"{where}.{side}: per-scale row")
            for label in ("D", "C"):
                component = item[label]
                require(isinstance(component, dict) and set(component) == {"kinetic", "gradient", "local", "total"}, f"{where}.{side}.{scale}.{label}")
                close(number(component["total"]), number(component["kinetic"]) + number(component["gradient"]) + number(component["local"]), f"{where}.{side}.{scale}.{label} closure", rel=2.0e-8, absolute=2.0e-8)
            close(number(item["total"]), number(item["kinetic"]) + number(item["gradient"]) + number(item["local"]), f"{where}.{side}.{scale} closure", rel=2.0e-8, absolute=2.0e-8)
            kinetic += number(item["kinetic"])
            gradient += number(item["gradient"])
            local += number(item["local"])
        close(kinetic, number(row["kinetic"]), f"{where}.{side}.kinetic", rel=2.0e-8, absolute=2.0e-8)
        close(gradient, number(row["gradient"]), f"{where}.{side}.gradient", rel=2.0e-8, absolute=2.0e-8)
        close(local, number(row["local"]), f"{where}.{side}.local", rel=2.0e-8, absolute=2.0e-8)
def _energy_map(value: Any, where: str) -> dict[str, float]:
    require(isinstance(value, dict), f"{where}: Hamiltonian object")
    expected = {"carrier", "topological", "extra_conservative", "link_energy", "total"}
    require(set(value) == expected, f"{where}: complete Hamiltonian components")
    return {key: number(value[key]) for key in expected}


def _check_rejected_work(
    receipt: Mapping[str, Any],
    *,
    center_pre_raw: bytes,
    center_post_raw: bytes,
    profile: Mapping[str, Any],
    root_obj: Mapping[str, Any],
    upstream: Mapping[str, Any],
    duration: float,
    control_id: str,
) -> None:
    """Recompute the attempted center map and its rejection work independently."""
    attempted = receipt.get("attempted_center_map_witness")
    expected_attempted = {
        "input_state_sha256",
        "output_state_sha256",
        "raw_domain",
        "layout",
        "layout_id",
        "shape",
        "dtype",
        "input",
        "output",
        "duration_s",
        "duration_rational",
        "lambda_rate",
        "tau",
        "candidate_state_sha256",
    }
    require(
        isinstance(attempted, dict) and set(attempted) == expected_attempted,
        f"{control_id}: attempted center witness schema",
    )
    scales, modes, _, _, _, _, _ = _layout(root_obj)
    _, input_batch = _decode(center_pre_raw, _layout(root_obj))
    _, output_batch = _decode(center_post_raw, _layout(root_obj))
    require(input_batch == output_batch, f"{control_id}: attempted center witness batch")
    expected_layout = {
        "scale_count": scales,
        "mode_count": modes,
        "component_count": 9,
        "shape": [scales, 9 * modes, input_batch],
    }
    require(attempted["raw_domain"] == RAW_DOMAIN.decode() and attempted["dtype"] == "<f8", f"{control_id}: attempted center witness encoding")
    require(attempted["layout_id"] == "cassi.qi-flow-state-layout.v3" and attempted["layout"] == expected_layout, f"{control_id}: attempted center witness layout")
    require(attempted["shape"] == expected_layout["shape"], f"{control_id}: attempted center witness shape")
    require(attempted["input_state_sha256"] == raw_hash(center_pre_raw) and attempted["output_state_sha256"] == raw_hash(center_post_raw), f"{control_id}: attempted center witness identity")
    require(attempted["candidate_state_sha256"] is None and number(attempted["tau"]) == 0.0, f"{control_id}: attempted center candidate/EMA")
    close(number(attempted["duration_s"]), duration, f"{control_id}: attempted center duration", absolute=0.0)
    duration_pair = _duration_value(duration, _duration_records(profile))[1]
    require(attempted["duration_rational"] == {"numerator": duration_pair[0], "denominator": duration_pair[1]}, f"{control_id}: attempted center duration rational")
    close(number(attempted["lambda_rate"]), number(profile.get("lambda_rate")), f"{control_id}: attempted center lambda", absolute=0.0)
    for label, descriptor, raw, role in (
        ("input", attempted["input"], center_pre_raw, "center-map-input"),
        ("output", attempted["output"], center_post_raw, "center-map-output"),
    ):
        require(isinstance(descriptor, dict), f"{control_id}: attempted {label} descriptor")
        require(
            set(descriptor)
            == {
                "role",
                "raw_domain",
                "domain",
                "dtype",
                "byte_order",
                "shape",
                "layout_id",
                "state_layout",
                "byte_count",
                "sha256",
                "raw_sha256",
            },
            f"{control_id}: attempted {label} descriptor schema",
        )
        require(descriptor["role"] == role and descriptor["raw_domain"] == RAW_DOMAIN.decode() and descriptor["domain"] == RAW_DOMAIN.decode() and descriptor["dtype"] == "<f8" and descriptor["byte_order"] == "little", f"{control_id}: attempted {label} descriptor metadata")
        require(descriptor["state_layout"] == expected_layout and descriptor["layout_id"] == attempted["layout_id"] and descriptor["shape"] == expected_layout["shape"], f"{control_id}: attempted {label} descriptor layout")
        require(descriptor["byte_count"] == len(raw) and descriptor["sha256"] == sha(raw) and descriptor["raw_sha256"] == raw_hash(raw), f"{control_id}: attempted {label} descriptor identity")
    map_replay = _replay_map(
        center_pre_raw,
        profile,
        root_obj,
        duration,
        lambda_rate=number(attempted["lambda_rate"]),
        tau_override=0.0,
    )
    _check_values(
        _decode(center_post_raw, _layout(root_obj))[0],
        map_replay["final"],
        f"{control_id}: rejected center map",
    )
    energy = receipt.get("energy")
    require(isinstance(energy, dict), f"{control_id}: rejected work energy")
    before = _energy_map(energy.get("hamiltonian_before"), f"{control_id}: rejected energy before")
    after = _energy_map(energy.get("hamiltonian_after"), f"{control_id}: rejected energy after")
    center_before = _energy_map(
        energy.get("center_hamiltonian_before"),
        f"{control_id}: rejected center energy before",
    )
    center_after = _energy_map(
        energy.get("center_hamiltonian_after"),
        f"{control_id}: rejected center energy after",
    )
    expected_before = _energy_from_raw(center_pre_raw, root_obj, upstream)
    expected_after = _energy_from_raw(center_post_raw, root_obj, upstream)
    for key in before:
        close(before[key], expected_before[key], f"{control_id}: rejected before.{key}", rel=2.0e-8, absolute=2.0e-8)
        close(after[key], expected_after[key], f"{control_id}: rejected after.{key}", rel=2.0e-8, absolute=2.0e-8)
        close(center_before[key], expected_before[key], f"{control_id}: rejected center before.{key}", rel=2.0e-8, absolute=2.0e-8)
        close(center_after[key], expected_after[key], f"{control_id}: rejected center after.{key}", rel=2.0e-8, absolute=2.0e-8)
    require(before == center_before and after == center_after and energy.get("pre") == before and energy.get("post") == after, f"{control_id}: rejected energy alias mismatch")
    delta_row = energy.get("delta")
    require(isinstance(delta_row, dict) and set(delta_row) == set(before), f"{control_id}: rejected energy delta")
    for key in before:
        close(number(delta_row[key]), after[key] - before[key], f"{control_id}: rejected delta.{key}", rel=2.0e-8, absolute=2.0e-8)
    require(energy.get("complete_component_recomputation") is True, f"{control_id}: incomplete rejected Hamiltonian")
    require(energy.get("candidate_state_sha256") is None, f"{control_id}: rejected candidate witness")
    uncertainty = _work_uncertainty(profile)
    delta = number(profile.get("margins", {}).get("Delta_conversion"))
    work = number(energy.get("W_conversion"))
    close(work, after["total"] - before["total"], f"{control_id}: rejected W_conversion", rel=2.0e-8, absolute=2.0e-8)
    close(
        number(energy.get("conversion_work_closure_abs")),
        abs((after["total"] - before["total"]) - work),
        f"{control_id}: rejected work closure",
        rel=2.0e-8,
        absolute=2.0e-8,
    )
    close(
        number(energy.get("full_step_hamiltonian_delta")),
        after["total"] - before["total"],
        f"{control_id}: rejected full-step delta",
        rel=2.0e-8,
        absolute=2.0e-8,
    )
    witness = receipt.get("work_witness")
    require(isinstance(witness, dict), f"{control_id}: rejected work witness")
    rejection_witness = receipt.get("work_rejection_witness")
    require(
        isinstance(rejection_witness, dict)
        and set(rejection_witness)
        == {"energy", "work", "attempted_center_map_witness", "candidate_state_sha256"}
        and rejection_witness["energy"] == energy
        and rejection_witness["work"] == witness
        and rejection_witness["attempted_center_map_witness"] == attempted
        and rejection_witness["candidate_state_sha256"] is None,
        f"{control_id}: rejected witness binding",
    )
    require(
        set(witness)
        == {
            "W_conversion",
            "U_conversion",
            "Delta_conversion",
            "interval_lower",
            "interval_upper",
            "classification",
            "Q_conversion",
            "sink",
            "accepted",
            "rejection_reason",
        },
        f"{control_id}: rejected work witness schema",
    )
    for energy_key, witness_key in (
        ("W_conversion", "W_conversion"),
        ("U_conversion", "U_conversion"),
        ("Delta_conversion", "Delta_conversion"),
        ("work_interval_lower", "interval_lower"),
        ("work_interval_upper", "interval_upper"),
    ):
        close(number(witness[witness_key]), number(energy[energy_key]), f"{control_id}: rejected work witness.{witness_key}", rel=2.0e-12, absolute=2.0e-12)
    require(witness["classification"] == energy.get("work_classification"), f"{control_id}: rejected classification binding")
    require(witness["Q_conversion"] is None and energy.get("Q_conversion") is None, f"{control_id}: rejected Q")
    require(witness["sink"] is False and energy.get("sink_recorded") is False, f"{control_id}: rejected sink")
    require(witness["accepted"] is False, f"{control_id}: rejected work accepted")
    if control_id == "positive-work-reject":
        require(witness["classification"] == "resolved-positive" and work - uncertainty > delta, f"{control_id}: unresolved positive work")
    else:
        require(control_id == "source-ambiguous-work", f"{control_id}: unexpected rejected work control")
        require(
            witness["classification"] == "source-ambiguous"
            and work - uncertainty <= delta
            and work + uncertainty >= -delta,
            f"{control_id}: source-ambiguous interval",
        )
    rejection = witness["rejection_reason"]
    require(isinstance(rejection, str) and rejection, f"{control_id}: rejection reason")
    require(receipt.get("work_rejection_witness", {}).get("work") == witness, f"{control_id}: work rejection witness binding")


def _check_energy(
    energy: Mapping[str, Any],
    *,
    predecessor_raw: bytes,
    candidate_raw: bytes,
    center_pre_raw: bytes | None,
    center_post_raw: bytes | None,
    root_obj: Mapping[str, Any],
    upstream: Mapping[str, Any],
    profile: Mapping[str, Any],
    where: str,
) -> None:
    require(isinstance(energy, dict), f"{where}: energy object")
    before = _energy_map(energy.get("hamiltonian_before"), f"{where}.hamiltonian_before")
    after = _energy_map(energy.get("hamiltonian_after"), f"{where}.hamiltonian_after")
    expected_before = _energy_from_raw(predecessor_raw, root_obj, upstream)
    expected_after = _energy_from_raw(candidate_raw, root_obj, upstream)
    for key in before:
        close(before[key], expected_before[key], f"{where}.before.{key}", rel=2.0e-8, absolute=2.0e-8)
        close(after[key], expected_after[key], f"{where}.after.{key}", rel=2.0e-8, absolute=2.0e-8)
    center_before = center_after = None
    if center_pre_raw is not None or center_post_raw is not None:
        require(center_pre_raw is not None and center_post_raw is not None, f"{where}: incomplete center fixtures")
        center_before = _energy_map(energy.get("center_hamiltonian_before"), f"{where}.center_before")
        center_after = _energy_map(energy.get("center_hamiltonian_after"), f"{where}.center_after")
        expected_center_before = _energy_from_raw(center_pre_raw, root_obj, upstream)
        expected_center_after = _energy_from_raw(center_post_raw, root_obj, upstream)
        for key in center_before:
            close(center_before[key], expected_center_before[key], f"{where}.center_before.{key}", rel=2.0e-8, absolute=2.0e-8)
            close(center_after[key], expected_center_after[key], f"{where}.center_after.{key}", rel=2.0e-8, absolute=2.0e-8)
    else:
        require("center_hamiltonian_before" not in energy and "center_hamiltonian_after" not in energy, f"{where}: center fixtures required")
    require(energy.get("extra_conservative_law_id") is None, f"{where}: unexpected extra conservative law")
    require(energy.get("duplicate_composition_or_topology_accounting") is False, f"{where}: duplicate energy accounting")
    work = number(energy.get("W_conversion"))
    require(center_before is not None and center_after is not None, f"{where}: center Hamiltonian missing")
    close(work, center_after["total"] - center_before["total"], f"{where}: W_conversion", rel=2.0e-8, absolute=2.0e-8)
    full_delta = number(energy.get("full_step_hamiltonian_delta"))
    close(full_delta, after["total"] - before["total"], f"{where}: full-step Hamiltonian delta", rel=2.0e-8, absolute=2.0e-8)
    close(number(energy.get("conversion_work_closure_abs")), abs((center_after["total"] - center_before["total"]) - work), f"{where}: conversion closure", rel=2.0e-8, absolute=2.0e-8)
    uncertainty = _work_uncertainty(profile)
    delta = number(profile.get("margins", {}).get("Delta_conversion"))
    classification = energy.get("work_classification")
    require(classification in {"resolved-dissipation", "numerical-zero"}, f"{where}: work classification")
    if classification == "resolved-dissipation":
        require(work + uncertainty < -delta, f"{where}: dissipation interval")
        close(number(energy.get("Q_conversion")), -work, f"{where}: Q_conversion", rel=2.0e-8, absolute=2.0e-8)
        require(energy.get("sink_recorded") is True, f"{where}: dissipation sink")
    else:
        require(work - uncertainty >= -delta and work + uncertainty <= delta, f"{where}: numerical-zero interval")
        close(number(energy.get("Q_conversion")), 0.0, f"{where}: numerical-zero Q", absolute=2.0e-8)
        require(energy.get("sink_recorded") is False, f"{where}: numerical-zero sink")


def _work_policy(receipt: Mapping[str, Any], control_id: str, profile: Mapping[str, Any]) -> None:
    energy = receipt.get("energy")
    require(isinstance(energy, dict), f"{control_id}: complete energy ledger required")
    classification = energy.get("work_classification")
    work = number(energy.get("W_conversion"))
    uncertainty = _work_uncertainty(profile)
    delta = number(profile.get("margins", {}).get("Delta_conversion"))
    if control_id == "positive-work-reject":
        require(work - uncertainty > delta and classification not in {"resolved-dissipation", "numerical-zero"}, f"{control_id}: positive work not unresolved")
        require(receipt.get("committable") is False or receipt.get("status") in {"REJECTED", "REJECT"}, f"{control_id}: positive work accepted")
    elif control_id == "negative-work-dissipative":
        require(classification == "resolved-dissipation" and work + uncertainty < -delta, f"{control_id}: dissipative work")
        require(receipt.get("committable") is True and receipt.get("status") == "PASS", f"{control_id}: dissipative work not accepted")
    elif control_id == "numerical-zero-work":
        require(classification == "numerical-zero" and work - uncertainty >= -delta and work + uncertainty <= delta, f"{control_id}: nonzero work")
    elif control_id == "source-ambiguous-work":
        require(work - uncertainty <= delta and work + uncertainty >= -delta and not (work + uncertainty < -delta) and not (work - uncertainty > delta), f"{control_id}: work is not source ambiguous")
        require(receipt.get("committable") is False or receipt.get("status") in {"REJECTED", "REJECT"}, f"{control_id}: ambiguous work accepted")


def _clock_summary(value: Any, where: str, *, allow_none: bool = False) -> dict[str, float] | None:
    if value is None and allow_none:
        return None
    require(isinstance(value, dict) and set(value) == {"min", "max", "mean"}, f"{where}: min/max/mean mapping required")
    summary = {key: number(value[key]) for key in ("min", "max", "mean")}
    require(summary["min"] <= summary["mean"] <= summary["max"], f"{where}: aggregate bounds")
    return summary


def _check_process_clock(
    receipt: Mapping[str, Any],
    *,
    duration: float,
    enabled: bool,
    conversion: Mapping[str, Any],
    control_id: str,
) -> None:
    process = receipt.get("process_clock")
    require(isinstance(process, dict), f"{control_id}: process-clock receipt")
    require(process.get("schema") == "cassi.qi-flow-process-clock.v1", f"{control_id}: process-clock schema")
    close(number(process.get("coordinate_duration_s")), duration, f"{control_id}: process-clock coordinate duration")
    require(process.get("coordinate_duration_rational") == receipt.get("duration_rational"), f"{control_id}: process-clock duration rational")
    require(process.get("coordinate_time_ground_truth") is True, f"{control_id}: coordinate time ground truth")
    require(process.get("normalization") == "d tau_F=(1-Q) dt; Delta tau_F=(1-Q) h; Delta chi_F=lambda*Delta tau_F", f"{control_id}: process-clock normalization")
    provenance = process.get("normalization_provenance")
    require(isinstance(provenance, dict) and provenance.get("law_id") == LAW_DOMAIN and provenance.get("coordinate_time") == "dt" and provenance.get("source") == "single frozen-Q conversion map", f"{control_id}: process-clock provenance")
    number(provenance.get("epsilon_guard"))
    rate = number(conversion.get("lambda_rate"))
    require(rate >= 0.0, f"{control_id}: process-clock lambda rate")
    close(number(process.get("lambda_rate")), rate, f"{control_id}: process-clock lambda rate")
    rate_bounds = process.get("lambda_rate_bounds")
    require(isinstance(rate_bounds, dict), f"{control_id}: process-clock rate bounds")
    close(number(rate_bounds.get("min")), rate, f"{control_id}: process-clock rate lower bound")
    close(number(rate_bounds.get("max")), rate, f"{control_id}: process-clock rate upper bound")
    conversion_rows = conversion.get("rows")
    rows = process.get("rows")
    require(isinstance(conversion_rows, list) and isinstance(rows, list) and len(rows) == len(conversion_rows) > 0, f"{control_id}: process-clock row coverage")
    require(process.get("conversion_row_count") == len(conversion_rows) and process.get("evaluation_count") == len(rows) and process.get("one_process_age_evaluation_per_conversion_row") is True, f"{control_id}: process-clock evaluation count")
    row_keys = {
        "scale", "sample_count", "q", "lambda_rate", "delta_tau_F", "delta_chi_F",
        "tau_F_defined", "chi_F_defined", "tau_F_expected", "chi_F_expected",
        "tau_F_endpoint", "chi_F_endpoint", "alpha_expected", "alpha_endpoint",
        "alpha_closure_abs", "tau_F_closure_abs", "chi_F_closure_abs",
        "endpoint_observable", "tau_F_endpoint_observable", "chi_F_endpoint_observable",
        "epsilon_pre_nonzero_count", "epsilon_post_nonzero_count",
        "endpoint_resolved_count", "endpoint_unresolved_count", "endpoint_degeneracy",
        "degeneracy_reasons",
    }
    parsed: list[dict[str, Any]] = []
    for index, (row, conversion_row) in enumerate(zip(rows, conversion_rows, strict=True)):
        require(isinstance(row, dict) and set(row) == row_keys and isinstance(conversion_row, dict), f"{control_id}: process-clock row {index} shape")
        require(row.get("scale") == conversion_row.get("scale"), f"{control_id}: process-clock row {index} scale")
        sample_count = row.get("sample_count")
        require(isinstance(sample_count, int) and not isinstance(sample_count, bool) and sample_count > 0, f"{control_id}: process-clock row {index} sample count")
        q = _clock_summary(row.get("q"), f"{control_id}: process-clock row {index} q")
        assert q is not None
        close(q["min"], number(conversion_row.get("q_min")), f"{control_id}: process-clock row {index} q minimum")
        close(q["max"], number(conversion_row.get("q_max")), f"{control_id}: process-clock row {index} q maximum")
        require(0.0 <= q["min"] <= q["max"] < 1.0, f"{control_id}: process-clock row {index} Q bounds")
        close(number(row.get("lambda_rate")), rate, f"{control_id}: process-clock row {index} lambda rate")
        tau = _clock_summary(row.get("delta_tau_F"), f"{control_id}: process-clock row {index} Delta tau_F")
        chi = _clock_summary(row.get("delta_chi_F"), f"{control_id}: process-clock row {index} Delta chi_F")
        tau_expected = _clock_summary(row.get("tau_F_expected"), f"{control_id}: process-clock row {index} tau_F expected")
        chi_expected = _clock_summary(row.get("chi_F_expected"), f"{control_id}: process-clock row {index} chi_F expected")
        assert tau is not None and chi is not None and tau_expected is not None and chi_expected is not None
        require(row.get("tau_F_defined") is True, f"{control_id}: process-clock row {index} defined conversion age")
        close(tau["min"], (1.0 - q["max"]) * duration, f"{control_id}: process-clock row {index} Delta tau_F minimum")
        close(tau["max"], (1.0 - q["min"]) * duration, f"{control_id}: process-clock row {index} Delta tau_F maximum")
        close(tau["mean"], (1.0 - q["mean"]) * duration, f"{control_id}: process-clock row {index} Delta tau_F mean")
        require(row.get("chi_F_defined") is True, f"{control_id}: process-clock row {index} chi_F defined")
        for key in ("min", "max", "mean"):
            close(tau[key], tau_expected[key], f"{control_id}: process-clock row {index} tau_F expected {key}")
            close(chi[key], chi_expected[key], f"{control_id}: process-clock row {index} chi_F expected {key}")
            close(chi[key], tau[key] * rate, f"{control_id}: process-clock row {index} chi_F {key}")
        alpha = _clock_summary(row.get("alpha_expected"), f"{control_id}: process-clock row {index} alpha expected")
        assert alpha is not None
        close(alpha["min"], number(conversion_row.get("alpha_min")), f"{control_id}: process-clock row {index} alpha minimum")
        close(alpha["max"], number(conversion_row.get("alpha_max")), f"{control_id}: process-clock row {index} alpha maximum")
        tau_endpoint = _clock_summary(row.get("tau_F_endpoint"), f"{control_id}: process-clock row {index} tau_F endpoint", allow_none=True)
        chi_endpoint = _clock_summary(row.get("chi_F_endpoint"), f"{control_id}: process-clock row {index} chi_F endpoint", allow_none=True)
        alpha_endpoint = _clock_summary(row.get("alpha_endpoint"), f"{control_id}: process-clock row {index} alpha endpoint", allow_none=True)
        for key in ("alpha_closure_abs", "tau_F_closure_abs", "chi_F_closure_abs"):
            if row.get(key) is not None:
                require(number(row[key]) >= 0.0, f"{control_id}: process-clock row {index} {key}")
        counts = []
        for key in ("epsilon_pre_nonzero_count", "epsilon_post_nonzero_count", "endpoint_resolved_count", "endpoint_unresolved_count"):
            value = row.get(key)
            require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{control_id}: process-clock row {index} {key}")
            counts.append(value)
        resolved, unresolved = counts[-2:]
        require((tau_endpoint is not None) == (rate > 0.0 and resolved > 0), f"{control_id}: process-clock row {index} tau_F endpoint presence")
        require((chi_endpoint is not None) == (resolved > 0) and (alpha_endpoint is not None) == (resolved > 0), f"{control_id}: process-clock row {index} endpoint witness presence")
        require(
            (
                row.get("alpha_closure_abs") is not None,
                row.get("tau_F_closure_abs") is not None,
                row.get("chi_F_closure_abs") is not None,
            )
            == (True, rate > 0.0 and resolved > 0, resolved > 0),
            f"{control_id}: process-clock row {index} endpoint closure presence",
        )
        require(resolved + unresolved == sample_count and row.get("endpoint_observable") is (resolved > 0) and row.get("endpoint_degeneracy") is (unresolved > 0), f"{control_id}: process-clock row {index} endpoint counts")
        require(row.get("tau_F_endpoint_observable") is (rate > 0.0 and resolved > 0) and row.get("chi_F_endpoint_observable") is (resolved > 0), f"{control_id}: process-clock row {index} endpoint flags")
        reasons = row.get("degeneracy_reasons")
        require(isinstance(reasons, list) and all(isinstance(reason, str) and reason for reason in reasons), f"{control_id}: process-clock row {index} degeneracy reasons")
        if rate == 0.0:
            require(any(reason.startswith("lambda=0:") for reason in reasons), f"{control_id}: process-clock row {index} lambda=0 witness")
        if unresolved:
            require(any("epsilon" in reason for reason in reasons), f"{control_id}: process-clock row {index} epsilon witness")
        parsed.append({"sample_count": sample_count, "q": q, "delta_tau_F": tau, "delta_chi_F": chi, "row": row})

    def aggregate(field: str, *, allow_none: bool = False) -> dict[str, float] | None:
        values = [item[field] for item in parsed]
        if allow_none and all(value is None for value in values):
            return None
        require(all(value is not None for value in values), f"{control_id}: process-clock aggregate {field} presence")
        typed = [value for value in values if value is not None]
        total = sum(item["sample_count"] for item in parsed)
        return {
            "min": min(value["min"] for value in typed),
            "max": max(value["max"] for value in typed),
            "mean": math.fsum(value["mean"] * item["sample_count"] for value, item in zip(typed, parsed, strict=True)) / total,
        }

    for field in ("q", "delta_tau_F", "delta_chi_F"):
        process_field = "q_bounds" if field == "q" else field
        actual = _clock_summary(process.get(process_field), f"{control_id}: process-clock {process_field}")
        expected = aggregate(field)
        require((actual is None) == (expected is None), f"{control_id}: process-clock {field} aggregate presence")
        if actual is not None and expected is not None:
            for key in ("min", "max", "mean"):
                close(actual[key], expected[key], f"{control_id}: process-clock {field} aggregate {key}")
    resolved_total = sum(item["row"]["endpoint_resolved_count"] for item in parsed)
    unresolved_total = sum(item["row"]["endpoint_unresolved_count"] for item in parsed)
    require(process.get("resolved_endpoint_count") == resolved_total and process.get("unresolved_endpoint_count") == unresolved_total, f"{control_id}: process-clock endpoint totals")
    require(process.get("lambda_zero") is (rate == 0.0) and process.get("tau_F_defined") is True and process.get("chi_F_defined") is True, f"{control_id}: process-clock rate observability")
    require(process.get("endpoint_observable") is (resolved_total > 0) and process.get("endpoint_degenerate") is (unresolved_total > 0) and process.get("epsilon_near_zero") is (unresolved_total > 0), f"{control_id}: process-clock endpoint observability")
    require(process.get("observability") == {
        "delta_tau_F": True,
        "delta_chi_F": True,
        "endpoint_alpha": resolved_total > 0,
        "endpoint_tau_F": rate > 0.0 and resolved_total > 0,
        "endpoint_chi_F": resolved_total > 0,
    }, f"{control_id}: process-clock observability map")
    process_reasons = process.get("degeneracy_reasons")
    require(isinstance(process_reasons, list), f"{control_id}: process-clock degeneracy summary")
    if rate == 0.0:
        require(any(str(reason).startswith("lambda=0:") for reason in process_reasons), f"{control_id}: process-clock lambda=0 summary")
    if unresolved_total:
        require(any("epsilon" in str(reason) for reason in process_reasons), f"{control_id}: process-clock epsilon summary")
    closure_values = [
        number(item["row"][key])
        for item in parsed
        for key in ("alpha_closure_abs", "tau_F_closure_abs", "chi_F_closure_abs")
        if item["row"].get(key) is not None
    ]
    require(process.get("closure_finite") is True and closure_values, f"{control_id}: process-clock closure")
    close(number(process.get("closure_abs")), max(closure_values), f"{control_id}: process-clock closure aggregate")


def _check_receipt(
    receipt: Mapping[str, Any],
    *,
    predecessor_raw: bytes,
    candidate_raw: bytes,
    profile: Mapping[str, Any],
    profile_sha: str,
    root_sha: str,
    law_sha: str,
    duration: float,
    enabled: bool,
    control_id: str,
    layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float],
    root_obj: Mapping[str, Any],
    upstream: Mapping[str, Any],
    center_pre_raw: bytes | None = None,
    center_post_raw: bytes | None = None,
    rejected: bool = False,
    synthetic_duplicate: bool = False,
) -> None:
    self_hash(receipt, INTEGRATED_DOMAIN)
    require(receipt.get("schema") == INTEGRATED_DOMAIN, f"{control_id}: receipt schema")
    require(receipt.get("predecessor_state_sha256") == raw_hash(predecessor_raw), f"{control_id}: predecessor identity")
    if rejected and not synthetic_duplicate:
        require(receipt.get("committable") is False and receipt.get("status") in {"REJECT", "REJECTED"}, f"{control_id}: rejection receipt")
        if receipt.get("candidate_state_sha256") is not None:
            require(receipt.get("candidate_state_sha256") == raw_hash(candidate_raw), f"{control_id}: rejected candidate identity")
        require(candidate_raw == predecessor_raw, f"{control_id}: rejected transition mutated state")
        if control_id in {"positive-work-reject", "source-ambiguous-work"}:
            require(center_pre_raw is not None and center_post_raw is not None, f"{control_id}: rejected center fixtures")
            require(receipt.get("profile_sha256") == profile_sha and receipt.get("root_sha256") == root_sha and receipt.get("law_sha256") == law_sha, f"{control_id}: rejected receipt identities")
            require(receipt.get("parent_identities") == profile.get("parent_identities"), f"{control_id}: rejected parent identities")
            provenance = receipt.get("source_provenance")
            require(isinstance(provenance, dict) and isinstance(provenance.get("source"), dict), f"{control_id}: rejected source provenance")
            require(provenance["source"].get("raw_sha256") == sha(predecessor_raw) and provenance.get("source_sha256") == digest(provenance["source"], "cassi.qi-flow-w5-source-provenance.v1"), f"{control_id}: rejected source provenance identity")
            close(number(receipt.get("duration_s")), duration, f"{control_id}: rejected duration", absolute=0.0)
            require(receipt.get("duration_rational") == {"numerator": _duration_value(duration, _duration_records(profile))[1][0], "denominator": _duration_value(duration, _duration_records(profile))[1][1]}, f"{control_id}: rejected duration rational")
            _check_rejected_work(receipt, center_pre_raw=center_pre_raw, center_post_raw=center_post_raw, profile=profile, root_obj=root_obj, upstream=upstream, duration=duration, control_id=control_id)
        return
    require(receipt.get("status") == "PASS" and receipt.get("committable") is True, f"{control_id}: receipt decision")
    require(receipt.get("candidate_state_sha256") == raw_hash(candidate_raw), f"{control_id}: candidate identity")
    require(receipt.get("profile_sha256") == profile_sha and receipt.get("root_sha256") == root_sha and receipt.get("law_sha256") == law_sha, f"{control_id}: receipt identities")
    require(receipt.get("parent_identities") == profile.get("parent_identities"), f"{control_id}: parent identities")
    provenance = receipt.get("source_provenance")
    require(isinstance(provenance, dict) and isinstance(provenance.get("source"), dict), f"{control_id}: source provenance")
    require(provenance["source"].get("raw_sha256") == sha(predecessor_raw) and provenance.get("source_sha256") == digest(provenance["source"], "cassi.qi-flow-w5-source-provenance.v1"), f"{control_id}: source provenance identity")
    close(number(receipt.get("duration_s")), duration, f"{control_id}: duration", absolute=0.0)
    require(receipt.get("duration_rational") == {"numerator": _duration_value(duration, _duration_records(profile))[1][0], "denominator": _duration_value(duration, _duration_records(profile))[1][1]}, f"{control_id}: duration rational")
    expected_stage_order = [
        "preflight",
        "first_local_force_velocity_half_kick",
        "first_analytic_damped_spectral_half_propagation",
        "w5_frozen_q_position_conversion",
        "second_analytic_damped_spectral_half_propagation",
        "second_local_force_velocity_half_kick",
        "precommit",
        "w5_single_post_step_epsilon2_ema",
    ]
    require(receipt.get("stage_order") == expected_stage_order, f"{control_id}: exact stage order")
    carrier_receipt = receipt.get("carrier_split_receipt")
    require(isinstance(carrier_receipt, dict) and carrier_receipt.get("stage_schedule", {}).get("stages"), f"{control_id}: carrier split receipt")
    require(len(carrier_receipt["stage_schedule"]["stages"]) == 7, f"{control_id}: carrier stage count")
    topology = receipt.get("topology")
    require(isinstance(topology, dict) and topology.get("force_evaluations") == 2 and topology.get("force_in_both_conservative_half_kicks") is True, f"{control_id}: topology force placement")
    conversion = receipt.get("conversion")
    require(isinstance(conversion, dict) and conversion.get("enabled") is enabled and conversion.get("q_evaluations") == 1 and conversion.get("conversion_maps") == 1 and conversion.get("center_map_invocations") == 1, f"{control_id}: centered map invocation")
    require(isinstance(conversion.get("rows"), list) and len(conversion["rows"]) == layout[0], f"{control_id}: conversion rows")
    require(isinstance(conversion.get("phase_branches"), dict), f"{control_id}: phase branches")
    _check_process_clock(receipt, duration=duration, enabled=enabled, conversion=conversion, control_id=control_id)
    ema = receipt.get("ema")
    require(isinstance(ema, dict) and ema.get("invocations") == 1 and ema.get("updates") == (1 if receipt.get("ema", {}).get("enabled") else 0) and ema.get("post_step_only") is True, f"{control_id}: EMA placement")
    memory_time = number(profile.get("epsilon_memory_time_s"))
    close(number(ema.get("tau")), -math.expm1(-duration / memory_time) if ema.get("enabled") else 0.0, f"{control_id}: tau", absolute=2.0e-15)
    if not ema.get("enabled"):
        require(ema.get("joint_off") is True and isinstance(ema.get("joint_off_identity"), dict) and ema["joint_off_identity"].get("equal") is True, f"{control_id}: EMA joint-off")
    guards = receipt.get("guards")
    require(isinstance(guards, dict) and set(guards) == {"density_nonnegative", "density_conservation_abs", "work_closed", "no_projection", "no_clipping", "no_repair", "no_extra_persistent_state"}, f"{control_id}: guards")
    require(guards.get("density_nonnegative") is True and guards.get("work_closed") is True and guards.get("no_projection") is True and guards.get("no_clipping") is True and guards.get("no_repair") is True and guards.get("no_extra_persistent_state") is True, f"{control_id}: forbidden repair")
    require(number(guards.get("density_conservation_abs")) <= _support_limits(profile)[2], f"{control_id}: density guard")
    _check_energy(receipt.get("energy"), predecessor_raw=predecessor_raw, candidate_raw=candidate_raw, center_pre_raw=center_pre_raw, center_post_raw=center_post_raw, root_obj=root_obj, upstream=upstream, profile=profile, where=f"{control_id}: energy")
    _work_policy(receipt, control_id, profile)
    if center_pre_raw is not None and center_post_raw is not None:
        _phase_velocity_check(_decode(center_pre_raw, layout)[0], _decode(center_post_raw, layout)[0], layout, control_id)
    require(conversion.get("velocities_unchanged_by_map") is True, f"{control_id}: map velocity mutation")

def _control_duration(record: Mapping[str, Any], profile: Mapping[str, Any]) -> tuple[float, tuple[int, int]]:
    return _duration_value(record.get("duration", record.get("duration_s")), _duration_records(profile))


def _fixture_path(value: Any, where: str) -> str:
    if isinstance(value, dict):
        value = value.get("path")
    require(isinstance(value, str) and value.startswith("fixtures/") and ".." not in Path(value).parts, f"{where}: fixture path")
    return value


def _raw_fixture(root: Path, value: Any, where: str) -> bytes:
    return _read_bytes(root / _fixture_path(value, where), where)


def _check_descriptor(value: Any, raw: bytes, where: str) -> None:
    require(isinstance(value, dict) and set(value) == {"path", "byte_count", "sha256", "domain", "shape", "dtype"}, f"{where}: raw descriptor")
    require(value["byte_count"] == len(raw) and value["sha256"] == sha(raw) and value["domain"] == (RAW_DOMAIN.decode() if isinstance(RAW_DOMAIN, bytes) else RAW_DOMAIN) and value["dtype"] == "<f8", f"{where}: raw descriptor identity")
    require(isinstance(value["shape"], list) and len(value["shape"]) == 3 and all(isinstance(item, int) and item > 0 for item in value["shape"]), f"{where}: raw descriptor shape")
    require(len(raw) == 8 * value["shape"][0] * value["shape"][1] * value["shape"][2], f"{where}: raw descriptor byte shape")

def _check_ema_transition(before_raw: bytes, after_raw: bytes, *, profile: Mapping[str, Any], root_obj: Mapping[str, Any], duration: float, enabled: bool, where: str) -> None:
    before, batches = _decode(before_raw, _layout(root_obj))
    after, after_batches = _decode(after_raw, _layout(root_obj))
    require(batches == after_batches, f"{where}: EMA batch")
    scales, modes, _, _, _, _, _ = _layout(root_obj)
    tau = -math.expm1(-duration / number(profile["epsilon_memory_time_s"])) if enabled else 0.0
    for scale in range(scales):
        for mode in range(modes):
            for lane in range(batches):
                index = _idx(scale, 8, mode, lane, modes, batches, scales)
                yr = after[_idx(scale, 0, mode, lane, modes, batches, scales)]
                yi = after[_idx(scale, 1, mode, lane, modes, batches, scales)]
                ir = after[_idx(scale, 2, mode, lane, modes, batches, scales)]
                ii = after[_idx(scale, 3, mode, lane, modes, batches, scales)]
                epsilon = (math.hypot(yr, yi) - math.sqrt(number(profile["phi"])) * math.hypot(ir, ii)) * (math.hypot(yr, yi) + math.sqrt(number(profile["phi"])) * math.hypot(ir, ii))
                expected = (1.0 - tau) * before[index] + tau * epsilon * epsilon
                close(after[index], expected, f"{where}: EMA[{scale},{mode},{lane}]", rel=2.0e-10, absolute=2.0e-12)
                for component in range(8):
                    close(before[_idx(scale, component, mode, lane, modes, batches, scales)], after[_idx(scale, component, mode, lane, modes, batches, scales)], f"{where}: post-EMA state")


def _check_duplicate_rejection(record: Mapping[str, Any], receipt: Mapping[str, Any], candidate_raw: bytes, predecessor_raw: bytes) -> None:
    duplicate = record.get("duplicate_invocation")
    require(isinstance(duplicate, dict) and set(duplicate) == {"attempted", "committable", "reason", "mutated_receipt"}, "duplicate-invocation: duplicate witness")
    require(duplicate["attempted"] is True and duplicate["committable"] is False and isinstance(duplicate["reason"], str) and duplicate["reason"], "duplicate-invocation: duplicate rejection")
    require(record.get("committable") is False and record.get("core_committable") is True and record.get("candidate_exposed") is False and record.get("no_mutation_on_reject") is True, "duplicate-invocation: no-commit witness")
    require(candidate_raw != predecessor_raw, "duplicate-invocation: synthetic candidate must be distinct")
    mutated = duplicate["mutated_receipt"]
    require(isinstance(mutated, dict), "duplicate-invocation: mutated receipt")
    expected = json.loads(canonical(receipt).decode("utf-8"))
    carrier = expected.get("carrier_split_receipt")
    schedule = carrier.get("stage_schedule") if isinstance(carrier, dict) else None
    stages = schedule.get("stages") if isinstance(schedule, dict) else None
    require(isinstance(stages, list) and len(stages) > 1 and isinstance(stages[1], dict), "duplicate-invocation: original schedule")
    stages[1]["name"] = "centered_conversion_placeholder"
    require(mutated == expected, "duplicate-invocation: unexpected receipt mutation")
    require(mutated.get("schema") == INTEGRATED_DOMAIN and isinstance(mutated.get("carrier_split_receipt"), dict), "duplicate-invocation: mutated schedule schema")


def _check_direct_control(
    record: Mapping[str, Any],
    *,
    root: Path,
    profile: Mapping[str, Any],
    profile_sha: str,
    root_sha: str,
    law_sha: str,
    layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float],
    root_obj: Mapping[str, Any],
    upstream: Mapping[str, Any],
    integrated: bool = False,
) -> None:
    control_id = record.get("control_id")
    require(record.get("schema") == (INTEGRATED_SCHEMA if integrated else CONTROL_SCHEMA), f"{control_id}: control schema")
    require(control_id in DIRECT_CONTROL_IDS, "unknown direct control")
    duration, _ = _control_duration(record, profile)
    fixtures = record.get("fixtures")
    require(isinstance(fixtures, dict), f"{control_id}: fixtures")
    expected_decision = record.get("expected_decision", record.get("actual_decision", "PASS"))
    rejected = expected_decision in {"REJECT", "REJECTED"}
    synthetic_duplicate = (
        control_id == "duplicate-invocation"
        and isinstance(record.get("duplicate_invocation"), dict)
    )
    require(
        record.get("actual_decision") == ("REJECT" if rejected else "PASS"),
        f"{control_id}: actual decision",
    )
    if synthetic_duplicate:
        require(
            record.get("committable") is False
            and record.get("core_committable") is True
            and record.get("candidate_exposed") is False,
            f"{control_id}: duplicate commit flags",
        )
    elif rejected:
        require(
            record.get("committable") is False
            and record.get("core_committable") is False
            and record.get("candidate_exposed") is False,
            f"{control_id}: rejected commit flags",
        )
    else:
        require(
            record.get("committable") is True
            and record.get("core_committable") is True
            and record.get("candidate_exposed") is True,
            f"{control_id}: accepted commit flags",
        )
    predecessor_descriptor = fixtures.get("predecessor")
    require(_fixture_path(predecessor_descriptor, f"{control_id} predecessor") == f"fixtures/{control_id}-predecessor.f64le", f"{control_id}: predecessor fixture")
    predecessor_raw = _raw_fixture(root, predecessor_descriptor, f"{control_id} predecessor")
    candidate_descriptor = fixtures.get("candidate")
    if candidate_descriptor is None:
        require(rejected, f"{control_id}: candidate fixture missing")
        candidate_raw = predecessor_raw
    else:
        require(_fixture_path(candidate_descriptor, f"{control_id} candidate") == f"fixtures/{control_id}-candidate.f64le", f"{control_id}: candidate fixture")
        candidate_raw = _raw_fixture(root, candidate_descriptor, f"{control_id} candidate")
    _check_descriptor(predecessor_descriptor, predecessor_raw, f"{control_id} predecessor")
    _decode(predecessor_raw, layout)
    if candidate_descriptor is not None:
        _check_descriptor(candidate_descriptor, candidate_raw, f"{control_id} candidate")
    _decode(candidate_raw, layout)
    require(record.get("predecessor_raw_sha256") == sha(predecessor_raw), f"{control_id}: predecessor raw hash")
    if candidate_descriptor is None:
        require(record.get("candidate_raw_sha256") is None, f"{control_id}: absent candidate hash")
    else:
        require(record.get("candidate_raw_sha256") == sha(candidate_raw), f"{control_id}: candidate raw hash")
    receipt = record.get("receipt")
    require(isinstance(receipt, dict) and record.get("receipt_sha256") == sha(canonical(receipt)), f"{control_id}: receipt binding")
    require(record.get("receipt_self_sha256") == receipt.get("self_sha256"), f"{control_id}: receipt self binding")
    require(record.get("attempted_center_map_witness", {}) == receipt.get("attempted_center_map_witness", {}), f"{control_id}: attempted center witness binding")
    require(record.get("work_witness", {}) == receipt.get("work_witness", {}), f"{control_id}: work witness binding")
    require(record.get("work_rejection_witness", {}) == receipt.get("work_rejection_witness", {}), f"{control_id}: rejection witness binding")
    center_in_path, center_out_path = fixtures.get("center_map_input"), fixtures.get("center_map_output")
    center_pre_raw = center_post_raw = None
    if center_in_path is not None or center_out_path is not None:
        require(center_in_path is not None and center_out_path is not None, f"{control_id}: incomplete center map fixtures")
        require(_fixture_path(center_in_path, f"{control_id} center input") == f"fixtures/{control_id}-center-map-input.f64le", f"{control_id}: center input fixture")
        require(_fixture_path(center_out_path, f"{control_id} center output") == f"fixtures/{control_id}-center-map-output.f64le", f"{control_id}: center output fixture")
        center_pre_raw = _raw_fixture(root, center_in_path, f"{control_id} center input")
        center_post_raw = _raw_fixture(root, center_out_path, f"{control_id} center output")
        _check_descriptor(center_in_path, center_pre_raw, f"{control_id} center input")
        _check_descriptor(center_out_path, center_post_raw, f"{control_id} center output")
    enabled = bool(record.get("conversion_enabled", record.get("enabled", True)))
    _check_receipt(receipt, predecessor_raw=predecessor_raw, candidate_raw=candidate_raw, profile=profile, profile_sha=profile_sha, root_sha=root_sha, law_sha=law_sha, duration=duration, enabled=enabled, control_id=control_id, layout=layout, root_obj=root_obj, upstream=upstream, center_pre_raw=center_pre_raw, center_post_raw=center_post_raw, rejected=rejected, synthetic_duplicate=synthetic_duplicate)
    if rejected and not synthetic_duplicate:
        require(record.get("no_mutation_on_reject") is True, f"{control_id}: reject mutation witness")
        require(isinstance(record.get("complete_energy"), dict), f"{control_id}: rejected complete energy")
        energy_pre_raw, energy_post_raw = predecessor_raw, candidate_raw
        if control_id in {"positive-work-reject", "source-ambiguous-work"}:
            require(center_pre_raw is not None and center_post_raw is not None, f"{control_id}: rejected center energy fixtures")
            energy_pre_raw, energy_post_raw = center_pre_raw, center_post_raw
        _check_complete_energy(record["complete_energy"], predecessor_raw=energy_pre_raw, candidate_raw=energy_post_raw, root_obj=root_obj, upstream=upstream, where=f"{control_id}: complete energy")
        return
    if synthetic_duplicate:
        _check_duplicate_rejection(record, receipt, candidate_raw, predecessor_raw)
    require(record.get("stage_order") == receipt.get("stage_order") and record.get("stage_trace") == receipt.get("carrier_split_receipt", {}).get("stage_schedule") and record.get("analytic_q_alpha_t_rows") == receipt.get("conversion", {}).get("rows") and record.get("process_clock") == receipt.get("process_clock") and record.get("phase_branches") == receipt.get("conversion", {}).get("phase_branches") and record.get("ema_rows") == receipt.get("ema", {}).get("rows") and record.get("energy") == receipt.get("energy") and record.get("guards") == receipt.get("guards"), f"{control_id}: receipt witness binding")
    require(record.get("intermediate_state_keys") == sorted(["candidate_post_ema", "post_center_conversion", "post_first_kick", "post_first_spectral_pre_center", "post_second_kick_pre_ema", "post_second_spectral", "predecessor"]), f"{control_id}: intermediate inventory")
    if not synthetic_duplicate:
        require(record.get("no_mutation_on_reject") is False, f"{control_id}: reject mutation witness")
    require(isinstance(record.get("complete_energy"), dict), f"{control_id}: complete energy")
    _check_complete_energy(record["complete_energy"], predecessor_raw=predecessor_raw, candidate_raw=candidate_raw, root_obj=root_obj, upstream=upstream, where=f"{control_id}: complete energy")
    require(center_pre_raw is not None and center_post_raw is not None, f"{control_id}: center map fixtures")
    map_replay = _replay_map(center_pre_raw, profile, root_obj, duration, lambda_rate=number(receipt["conversion"]["lambda_rate"]), tau_override=0.0)
    _check_values(_decode(center_post_raw, layout)[0], map_replay["final"], f"{control_id}: centered frozen-Q map")
    conversion = receipt["conversion"]
    require(conversion.get("phase_branches") == map_replay["phase_counts"], f"{control_id}: phase branches")
    rows = conversion.get("rows")
    require(isinstance(rows, list) and len(rows) == layout[0], f"{control_id}: conversion rows")
    for scale, expected in enumerate(map_replay["rows"]):
        _check_row(rows[scale], expected, f"{control_id}: conversion[{scale}]")
    stage_pre_ema = fixtures.get("w4r_hamiltonian_topology")
    require(stage_pre_ema is not None, f"{control_id}: post-EMA input fixture")
    stage_pre_ema_raw = _raw_fixture(root, stage_pre_ema, f"{control_id} post-EMA input")
    _check_descriptor(stage_pre_ema, stage_pre_ema_raw, f"{control_id} post-EMA input")
    _check_ema_transition(stage_pre_ema_raw, candidate_raw, profile=profile, root_obj=root_obj, duration=duration, enabled=bool(receipt["ema"].get("enabled")), where=control_id)
    for fixture_name, descriptor in fixtures.items():
        if isinstance(descriptor, dict) and "path" in descriptor and fixture_name not in {"predecessor", "candidate", "center_map_input", "center_map_output", "w4r_hamiltonian_topology"}:
            raw = _raw_fixture(root, descriptor, f"{control_id} {fixture_name}")
            _check_descriptor(descriptor, raw, f"{control_id} {fixture_name}")
            _decode(raw, layout)
    if control_id == "lambda-off":
        _check_values(_decode(center_pre_raw, layout)[0], _decode(center_post_raw, layout)[0], f"{control_id}: map term disabled")
    if control_id == "lambda-and-ema-off":
        require(receipt["conversion"].get("enabled") is False and receipt["ema"].get("enabled") is False, f"{control_id}: joint-off flags")

def _check_row(actual: Mapping[str, Any], expected: Mapping[str, Any], where: str) -> None:
    require(isinstance(actual, dict) and set(actual) == set(expected), f"{where}: row schema")
    for key, expected_value in expected.items():
        if isinstance(expected_value, dict):
            require(isinstance(actual[key], dict) and actual[key] == expected_value, f"{where}.{key}")
        elif isinstance(expected_value, int):
            require(actual[key] == expected_value, f"{where}.{key}")
        else:
            close(number(actual[key]), float(expected_value), f"{where}.{key}", absolute=5.0e-10)


def _check_integrated(
    record: Mapping[str, Any],
    *,
    root: Path,
    profile: Mapping[str, Any],
    profile_sha: str,
    root_sha: str,
    law_sha: str,
    layout: tuple[int, int, int, int, tuple[tuple[int, int], ...], tuple[int, ...], float],
    root_obj: Mapping[str, Any],
    upstream: Mapping[str, Any],
) -> None:
    require(record.get("schema") == INTEGRATED_SCHEMA, "integrated control schema")
    self_hash(record, INTEGRATED_SCHEMA)
    control_id = record.get("control_id")
    require(control_id in DIRECT_CONTROL_IDS, "integrated control id")
    _check_direct_control(
        record,
        root=root,
        profile=profile,
        profile_sha=profile_sha,
        root_sha=root_sha,
        law_sha=law_sha,
        layout=layout,
        root_obj=root_obj,
        upstream=upstream,
        integrated=True,
    )


def _records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path == root / "index.json"
            or str(path.relative_to(root)).replace("\\", "/") == "gates/g05-conversion/conversion.json"
        ):
            continue
        raw = _read_bytes(path, f"artifact object {path}")
        records.append(
            {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "byte_count": len(raw),
                "sha256": sha(raw),
            }
        )
    return records


def _expected_paths(control_records: Mapping[str, Mapping[str, Any]] | None = None, integrated_records: Mapping[str, Mapping[str, Any]] | None = None) -> set[str]:
    paths = {
        "parents/w4r-parent-index.json",
        "parents/w4r-parent-candidate.json",
        "parents/w4r-parent-profile.json",
        "parents/w4r-parent-root.json",
        "parents/w4r-parent-extension-0003.json",
        "parents/ancestry.json",
        "certificate/g3n-certificate-root.json",
        "certificate/w4r-extension-0003.json",
        "profile/conversion-profile.json",
        "profile/conversion-root.json",
        "profile/conversion-law.json",
        "run-spec/parent-w4r.json",
        "run-spec/source-identity.json",
        "run-spec/upstream-profiles.json",
        "gates/g05-conversion/candidate.json",
        "gates/g05-conversion/status.json",
        "gates/g05-conversion/measurements.json",
        "gates/g05-conversion/deterministic-replay.json",
        "gates/g05-conversion/integrated-replay-a.json",
        "gates/g05-conversion/integrated-replay-b.json",
        "gates/g05-conversion/integrated-conversion-term-off.json",
    }
    paths.update(f"sources/{path}" for path in SOURCE_PATHS)
    for control_id in DIRECT_CONTROL_IDS:
        paths.add(f"gates/g05-conversion/controls/{control_id}.json")
    for records in (control_records or {}, integrated_records or {}):
        for record in records.values():
            fixtures = record.get("fixtures") if isinstance(record, dict) else None
            if isinstance(fixtures, dict):
                for descriptor in fixtures.values():
                    if isinstance(descriptor, dict) and isinstance(descriptor.get("path"), str):
                        paths.add(descriptor["path"])
    return paths


def _source_exact(root: Path) -> tuple[list[dict[str, Any]], str]:
    identity = read_json(root / "run-spec" / "source-identity.json")
    require(
        set(identity) == {"schema", "domain", "source_exact", "sources", "self_sha256"}
        and identity.get("schema") == SOURCE_IDENTITY_SCHEMA
        and identity.get("domain") == SOURCE_IDENTITY_SCHEMA
        and identity.get("source_exact") is True,
        "source identity schema",
    )
    self_hash(identity, SOURCE_IDENTITY_SCHEMA)
    records = identity.get("sources")
    require(isinstance(records, list) and tuple(item.get("path") for item in records) == SOURCE_PATHS, "source inventory exactness")
    for item in records:
        require(isinstance(item, dict) and set(item) == {"path", "byte_count", "sha256"}, "source record schema")
        snapshot = _read_bytes(root / "sources" / item["path"], f"source snapshot {item['path']}")
        live = _read_bytes(ROOT / item["path"], f"live source {item['path']}")
        require(snapshot == live and len(snapshot) == item["byte_count"] and sha(snapshot) == item["sha256"], f"source snapshot mismatch: {item['path']}")
    return records, identity["self_sha256"]


def _json_objects(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    result = []
    for candidate in sorted(path.rglob("*.json")):
        try:
            result.append((candidate, read_json(candidate)))
        except VerificationError:
            continue
    return result


def _normalise_verifier_result(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalise_verifier_result(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise_verifier_result(item) for item in value]
    if isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        return f64_tag(value)
    if value is None or isinstance(value, str):
        return value
    raise VerificationError(f"unsupported independent verifier result value: {type(value).__name__}")


def _w4r_verifier_receipt(parent_root: Path) -> dict[str, Any]:
    try:
        verifier = importlib.import_module("verify_cassi_qi_topology")
        public_verify = getattr(verifier, "verify")
    except (ImportError, AttributeError) as exc:
        raise VerificationError("W4R independent verifier unavailable") from exc
    result = public_verify(parent_root)
    normalized = _normalise_verifier_result(result)
    require(
        isinstance(normalized, dict)
        and normalized.get("status") == "PASS"
        and normalized.get("schema") == W4R_INDEX_SCHEMA,
        "W4R independent verifier did not pass",
    )
    return {
        "schema": PARENT_VERIFICATION_SCHEMA,
        "result": normalized,
        "verification_sha256": digest(normalized, PARENT_VERIFICATION_SCHEMA),
    }


def _parent_verifier_receipts(parent: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    receipt = parent.get("parent_verifier_receipt")
    require(isinstance(receipt, dict), "W4R independent verifier receipt missing")
    expected = {"schema": PARENT_VERIFIER_RECEIPTS_SCHEMA, "w4r": receipt}
    return expected, digest(expected, PARENT_VERIFIER_RECEIPTS_SCHEMA)

def _parent_identity_from_candidate(parent_root: Path) -> dict[str, Any]:
    index = read_json(parent_root / "index.json")

    if index.get("self_sha256") is not None:
        self_hash(index, W4R_INDEX_SCHEMA)
    require(
        index.get("schema") == W4R_INDEX_SCHEMA
        and index.get("artifact_domain", index.get("domain")) == W4R_ARTIFACT_DOMAIN
        and parent_root.name == index.get("run_id"),
        "W4R content-addressed index",
    )
    require(index.get("status") == "PASS_W4R_G4R", "W4R parent is not independently PASS")
    gate = parent_root / "gates" / "g04r-retention-core"
    status_path = gate / "status.json"
    require(gate.is_dir() and status_path.is_file(), "canonical W4R retention-core gate missing")
    status = read_json(status_path)
    require(status.get("status") == "PASS_W4R_G4R", "W4R gate status")
    gate_receipt_path = gate / "gate-receipt.json"
    require(gate_receipt_path.is_file(), "canonical W4R gate receipt missing")
    gate_receipt = read_json(gate_receipt_path)
    require(
        gate_receipt.get("schema") == W4R_ARTIFACT_DOMAIN + "-gate-receipt.v1"
        and gate_receipt.get("domain") == W4R_ARTIFACT_DOMAIN
        and gate_receipt.get("status") == "PASS_W4R_G4R"
        and gate_receipt.get("gate") == "G4R",
        "W4R gate receipt",
    )
    self_hash(gate_receipt, W4R_ARTIFACT_DOMAIN + ".gate-receipt")
    if index.get("gate_receipt_sha256") is not None:
        require(index["gate_receipt_sha256"] == gate_receipt["self_sha256"], "W4R gate receipt identity")
    source_path = parent_root / "run-spec" / "source-identity.json"
    require(source_path.is_file(), "W4R source identity missing")
    source_identity = read_json(source_path)
    if isinstance(source_identity.get("self_sha256"), str) and isinstance(source_identity.get("domain", source_identity.get("schema")), str):
        self_hash(source_identity, str(source_identity.get("domain", source_identity.get("schema"))))
    require(source_identity.get("schema") == "cassi.qi-flow-w4r-retention-core-source-identity.v1", "W4R source identity schema")
    if "source_exact" in source_identity:
        require(source_identity.get("source_exact") is True, "W4R source identity is not exact")
    source_records = source_identity.get("sources", source_identity.get("source_files"))
    require(isinstance(source_records, list) and source_records, "W4R source inventory missing")
    for item in source_records:
        require(isinstance(item, dict) and isinstance(item.get("path"), str), "W4R source record")
        relative = item["path"][len("sources/") :] if item["path"].startswith("sources/") else item["path"]
        snapshot = _read_bytes(parent_root / "sources" / relative, "W4R source snapshot")
        live = _read_bytes(ROOT / relative, "W4R live source")
        require(snapshot == live and sha(snapshot) == item.get("sha256") and len(snapshot) == item.get("byte_count"), "stale W4R source")
    objects = _json_objects(parent_root)
    candidates = [
        (path, obj)
        for path, obj in objects
        if "candidate" in str(obj.get("schema", "")).lower()
        and "parents/" not in path.relative_to(parent_root).as_posix()
    ]
    profiles = [
        (path, obj)
        for path, obj in objects
        if "profiles/" in path.relative_to(parent_root).as_posix()
        and isinstance(obj.get("profile_sha256"), str)
        and "parents/" not in path.relative_to(parent_root).as_posix()
    ]
    roots = [
        (path, obj)
        for path, obj in objects
        if "root" in str(obj.get("schema", "")).lower()
        and isinstance(obj.get("self_sha256"), str)
        and "parents/" not in path.relative_to(parent_root).as_posix()
    ]
    def extension_field(obj: Mapping[str, Any], key: str) -> Any:
        value = obj.get(key)
        if value is not None:
            return value
        nested = obj.get("extension")
        return nested.get(key) if isinstance(nested, dict) else None

    extensions = [
        (path, obj)
        for path, obj in objects
        if path.relative_to(parent_root).as_posix().startswith("certificate/")
        and "extension" in str(extension_field(obj, "schema")).lower()
        and isinstance(extension_field(obj, "self_sha256"), str)
    ]
    certificates = [
        (path, obj)
        for path, obj in objects
        if path.relative_to(parent_root).as_posix() == "certificate/g3n-certificate-root.json"
    ]
    require(len(certificates) == 1, "W4R G3N certificate root missing or ambiguous")
    certificate_path, _ = certificates[0]
    certificate_sha = sha(_read_bytes(certificate_path, "W4R G3N certificate root"))
    require(len(candidates) == 1 and len(profiles) == 1 and len(roots) == 1 and len(extensions) == 1, "W4R parent object ambiguity")
    candidate, profile, root_obj, extension = candidates[0][1], profiles[0][1], roots[0][1], extensions[0][1]
    candidate_sha = candidate.get("self_sha256")
    profile_sha = profile.get("profile_sha256")
    root_sha = root_obj.get("self_sha256")
    extension_sha = extension_field(extension, "self_sha256")
    for name, value in (("candidate", candidate_sha), ("profile", profile_sha), ("root", root_sha), ("extension", extension_sha)):
        require(isinstance(value, str) and len(value) == 64, f"W4R {name} identity")
    return {
        "root": parent_root,
        "run_id": index.get("run_id"),
        "index_sha256": sha(_read_bytes(parent_root / "index.json", "W4R index")),
        "candidate_sha256": candidate_sha,
        "profile_sha256": profile_sha,
        "root_sha256": root_sha,
        "extension_sha256": extension_sha,
        "certificate_sha256": certificate_sha,
        "certificate_path": certificate_path,
    }



def _discover_w4r(declared: Mapping[str, Any]) -> dict[str, Any]:
    diag = ROOT / "_diag"
    require(diag.is_dir(), "W4R diagnostic roots missing")
    roots: list[Path] = []
    for family in sorted(diag.glob("cassi-qi-flow-w4r*-final")):
        if (family / "index.json").is_file():
            roots.append(family)
        for child in sorted(family.iterdir()):
            if child.is_dir() and (child / "index.json").is_file():
                roots.append(child)
    candidates = []
    verification_cache: dict[Path, dict[str, Any]] = {}
    for root in roots:
        try:
            cache_key = root.resolve()
            if cache_key not in verification_cache:
                verification_cache[cache_key] = _w4r_verifier_receipt(root)
            current = _parent_identity_from_candidate(root)
            current["parent_verifier_receipt"] = verification_cache[cache_key]
            candidates.append(current)
        except (OSError, VerificationError, ValueError, TypeError, KeyError, ImportError):
            continue
    require(len(candidates) == 1, "W5 requires exactly one current source-exact W4R parent")
    current = candidates[0]
    for key in ("run_id", "index_sha256"):
        if declared.get(key) is not None:
            require(declared[key] == current.get(key), f"W4R declared {key} mismatch")
    if isinstance(declared.get("root"), str):
        require(Path(declared["root"]).resolve() == current["root"].resolve(), "W4R pinned/substituted root")
    return current


def _verify_parent(root: Path, declared: Mapping[str, Any]) -> dict[str, Any]:
    current = _discover_w4r(declared)
    require(declared.get("run_id") == current.get("run_id") and declared.get("index_sha256") == current.get("index_sha256"), "W4R parent identity")
    for key in ("candidate_sha256", "profile_sha256", "root_sha256", "extension_sha256"):
        if declared.get(key) is not None:
            require(declared[key] == current.get(key), f"W4R parent {key}")
    snapshots = {"parents/w4r-parent-index.json": current["root"] / "index.json"}
    for relative in ("parents/w4r-parent-candidate.json", "parents/w4r-parent-profile.json", "parents/w4r-parent-root.json", "parents/w4r-parent-extension-0003.json", "certificate/g3n-certificate-root.json", "certificate/w4r-extension-0003.json"):
        snapshot = read_json(root / relative)
        schema = str(snapshot.get("schema", ""))
        matches = [path for path, live in _json_objects(current["root"]) if live == snapshot or (schema and live.get("schema") == schema and live.get("self_sha256") == snapshot.get("self_sha256"))]
        require(len(matches) == 1, f"W4R parent object missing/ambiguous: {relative}")
        snapshots[relative] = matches[0]
    for relative, live_path in snapshots.items():
        require(_read_bytes(root / relative, relative) == _read_bytes(live_path, f"live {relative}"), f"stale/substituted W4R snapshot: {relative}")
    ancestry = read_json(root / "parents/ancestry.json")
    require(isinstance(ancestry, dict) and ancestry.get("w4r") == declared, "ancestry W4R identity mismatch")
    for key in ("w4", "w3n"):
        identity = ancestry.get(key)
        require(isinstance(identity, dict) and any(name.endswith("sha256") and isinstance(value, str) for name, value in identity.items()), f"unverified ancestry: {key}")
    w4_identity = declared.get("w4_identity")
    w3n_identity = declared.get("w3n_identity")
    receipt_result = current.get("parent_verifier_receipt", {}).get("result")
    require(ancestry.get("w4") == w4_identity and ancestry.get("w3n") == w3n_identity, "ancestry parent identity mismatch")
    require(isinstance(w4_identity, dict) and isinstance(w3n_identity, dict) and isinstance(receipt_result, dict), "W4/W3N ancestry provenance")
    require(
        receipt_result.get("parent_w4_run_id") == w4_identity.get("w4_run_id")
        and receipt_result.get("parent_w3n_run_id") == w3n_identity.get("w3n_run_id"),
        "W4/W3N ancestry verifier binding",
    )
    parent_verifier_receipts, parent_verifier_receipts_sha256 = _parent_verifier_receipts(current)
    require(
        declared.get("parent_verifier_receipt") == parent_verifier_receipts["w4r"]
        and declared.get("parent_verifier_receipts_sha256") == parent_verifier_receipts_sha256,
        "W4R parent verifier receipt provenance mismatch",
    )
    return {
        "run_id": current.get("run_id"),
        "index_sha256": current.get("index_sha256"),
        "candidate_sha256": current.get("candidate_sha256"),
        "profile_sha256": current.get("profile_sha256"),
        "root_sha256": current.get("root_sha256"),
        "extension_sha256": current.get("extension_sha256"),
        "preserved": True,
        "parent_verifier_receipts": parent_verifier_receipts,
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
    }


_ROOT_OBJECT: Mapping[str, Any] = {}


def verify(root: Path) -> dict[str, Any]:
    global _ROOT_OBJECT
    root = Path(root)
    require(root.is_dir(), "W5 artifact root missing")
    index = read_json(root / "index.json")
    require(index.get("schema") == INDEX_SCHEMA and root.name == index.get("run_id"), "W5 content-addressed index")
    require(index.get("status") == "PASS_W5_G5" and index.get("w5v_forward_domain_certificate") is None, "W5 index status")
    self_hash(index, ARTIFACT_DOMAIN)
    candidate = read_json(root / "gates/g05-conversion/candidate.json")
    status = read_json(root / "gates/g05-conversion/status.json")
    measurements = read_json(root / "gates/g05-conversion/measurements.json")
    deterministic = read_json(root / "gates/g05-conversion/deterministic-replay.json")
    controls = {control_id: read_json(root / "gates/g05-conversion/controls" / f"{control_id}.json") for control_id in DIRECT_CONTROL_IDS}
    integrated = {label: read_json(root / "gates/g05-conversion" / f"{label}.json") for label in INTEGRATED_LABELS}
    inventory_records = dict(controls)
    inventory_records.update({"deterministic-a": deterministic.get("replay_a", {}), "deterministic-b": deterministic.get("replay_b", {})})
    actual_records = _records(root)
    object_records = index.get("objects")
    require(isinstance(object_records, list) and object_records == actual_records, "raw content-addressed object inventory")
    require({record.get("path") for record in object_records} == _expected_paths(inventory_records, integrated), "extra/missing W5 object")
    parent_declared = read_json(root / "run-spec/parent-w4r.json")
    parent = _verify_parent(root, parent_declared)
    parent_verifier_receipts = parent["parent_verifier_receipts"]
    parent_verifier_receipts_sha256 = parent["parent_verifier_receipts_sha256"]
    require(
        index.get("parent_verifier_receipts") == parent_verifier_receipts
        and index.get("parent_verifier_receipts_sha256") == parent_verifier_receipts_sha256,
        "W5 index parent verifier receipt binding",
    )
    _, source_identity_sha = _source_exact(root)
    profile = read_json(root / "profile/conversion-profile.json")
    conversion_root = read_json(root / "profile/conversion-root.json")
    law = read_json(root / "profile/conversion-law.json")
    self_hash(profile, PROFILE_DOMAIN)
    self_hash(conversion_root, ROOT_DOMAIN)
    require(law == profile.get("law") and digest(law, LAW_DOMAIN) == profile.get("law_sha256"), "conversion law identity")
    require(profile.get("schema") == PROFILE_DOMAIN and conversion_root.get("schema") == ROOT_DOMAIN and law.get("law_id") == LAW_DOMAIN, "core W5 object domains")
    upstream = _upstream_profiles(root)
    durations = _duration_records(profile)
    layout = _layout(conversion_root)
    _ROOT_OBJECT = conversion_root
    profile_sha, root_sha, law_sha = profile["profile_sha256"], conversion_root["self_sha256"], profile["law_sha256"]
    require(index.get("profile_sha256") == profile_sha and index.get("root_sha256") == root_sha and index.get("law_sha256") == law_sha and index.get("conversion_profile_sha256") == profile_sha and index.get("conversion_root_sha256") == root_sha and index.get("conversion_law_sha256") == law_sha, "index profile/root/law linkage")
    require(index.get("parents") == [parent_declared] and index.get("source_exact_successor_of") == parent_declared, "index ancestry binding")
    require(profile.get("parent_identities", {}).get("w4r_candidate_sha256") == parent.get("candidate_sha256"), "profile W4R candidate identity")
    require(profile.get("parent_identities", {}).get("w4r_topology_profile_sha256") == parent.get("profile_sha256"), "profile W4R topology identity")
    self_hash(status, STATUS_SCHEMA)
    require(
        status.get("schema") == STATUS_SCHEMA
        and status.get("gate") == "G5"
        and status.get("status") == "PASS_W5_G5"
        and status.get("decision") == "PASS"
        and status.get("control_inventory_exact") == list(DIRECT_CONTROL_IDS)
        and status.get("all_expected_decisions") is True
        and status.get("integrated_centered_split") is True
        and status.get("dynamic_source_exact_ancestry") is True
        and status.get("engineering_candidate_only") is True
        and status.get("w5v_forward_domain_certificate") is None
        and status.get("parent_verifier_receipts") == parent_verifier_receipts
        and status.get("parent_verifier_receipts_sha256") == parent_verifier_receipts_sha256,
        "G5 status",
    )
    self_hash(measurements, MEASUREMENTS_SCHEMA)
    require(measurements.get("schema") == MEASUREMENTS_SCHEMA and measurements.get("domain") == MEASUREMENTS_SCHEMA and measurements.get("w5v_forward_domain_certificate") is None and measurements.get("controls") == controls, "measurements binding")
    self_hash(candidate, CANDIDATE_SCHEMA)
    require(candidate.get("schema") == CANDIDATE_SCHEMA and candidate.get("status") == "PASS" and candidate.get("candidate_only") is True and candidate.get("extension_added") is False and candidate.get("w5v_forward_domain_certificate") is None and candidate.get("profile_sha256") == profile_sha and candidate.get("root_sha256") == root_sha and candidate.get("law_sha256") == law_sha and candidate.get("parent_identities") == profile.get("parent_identities") and candidate.get("measurements_sha256") == measurements.get("self_sha256"), "candidate identity")
    require(candidate.get("status_path") == "gates/g05-conversion/status.json" and candidate.get("measurements_path") == "gates/g05-conversion/measurements.json" and candidate.get("status_sha256") == status.get("self_sha256"), "candidate status links")
    for control_id in DIRECT_CONTROL_IDS:
        record = controls[control_id]
        self_hash(record, CONTROL_SCHEMA)
        require(record.get("expected_decision") == record.get("actual_decision"), f"{control_id}: expected decision")
        _check_direct_control(record, root=root, profile=profile, profile_sha=profile_sha, root_sha=root_sha, law_sha=law_sha, layout=layout, root_obj=conversion_root, upstream=upstream)
    require(deterministic.get("schema") == INTEGRATED_SCHEMA and deterministic.get("same_predecessor") is True and deterministic.get("one_integrated_invocation_per_record") is True and deterministic.get("no_duplicate_full_step") is True, "direct deterministic replay")
    replay_a, replay_b = deterministic.get("replay_a"), deterministic.get("replay_b")
    require(isinstance(replay_a, dict) and isinstance(replay_b, dict) and replay_a.get("control_id") == "duplicate-invocation" and replay_b.get("control_id") == "balanced", "deterministic replay records")
    require(replay_a.get("receipt_sha256") == controls["duplicate-invocation"].get("receipt_sha256") and replay_b.get("receipt_sha256") == controls["balanced"].get("receipt_sha256"), "deterministic receipt binding")
    require(replay_a.get("center_map_invocations") == 1 and replay_b.get("center_map_invocations") == 1, "deterministic centered map count")
    require(_raw_fixture(root, controls["duplicate-invocation"]["fixtures"]["predecessor"], "replay A predecessor") == _raw_fixture(root, controls["balanced"]["fixtures"]["predecessor"], "replay B predecessor"), "deterministic predecessor")
    for label, record in integrated.items():
        _check_integrated(record, root=root, profile=profile, profile_sha=profile_sha, root_sha=root_sha, law_sha=law_sha, layout=layout, root_obj=conversion_root, upstream=upstream)
    require(candidate.get("control_id") in DIRECT_CONTROL_IDS and controls[candidate["control_id"]].get("candidate_raw_sha256") == candidate.get("candidate_raw_sha256") and controls[candidate["control_id"]].get("receipt_sha256") == candidate.get("receipt_sha256"), "candidate witness binding")
    material = {
        "schema": INDEX_SCHEMA,
        "status": status["status"],
        "parents": [parent_declared],
        "source_exact_successor_of": parent_declared,
        "profile_sha256": profile_sha,
        "root_sha256": root_sha,
        "law_sha256": law_sha,
        "conversion_profile_sha256": profile_sha,
        "conversion_root_sha256": root_sha,
        "conversion_law_sha256": law_sha,
        "candidate_sha256": candidate["self_sha256"],
        "status_sha256": status["self_sha256"],
        "measurements_sha256": measurements["self_sha256"],
        "engineering_candidate_only": True,
        "parent_verifier_receipts": parent_verifier_receipts,
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
        "w5v_forward_domain_certificate": None,
        "objects": object_records,
    }
    require(index.get("run_id") == digest(material, ARTIFACT_DOMAIN), "content-addressed run id")
    _reject_w5v(index)
    return {
        "gate": "G5",
        "status": "PASS_W5_G5",
        "run_id": index["run_id"],
        "index_sha256": sha(_read_bytes(root / "index.json", "W5 index")),
        "conversion_profile_sha256": profile_sha,
        "conversion_root_sha256": root_sha,
        "law_sha256": law_sha,
        "source_identity_sha256": source_identity_sha,
        "parent": parent,
        "parent_verifier_receipts": parent_verifier_receipts,
        "parent_verifier_receipts_sha256": parent_verifier_receipts_sha256,
        "registered_durations_s": [n / d for n, d in durations],
        "lambda_rate_s_inv": number(profile["lambda_rate"]),
        "rho_ref": number(profile["rho_ref"]),
        "epsilon_memory_time_s": number(profile["epsilon_memory_time_s"]),
        "phi": number(profile["phi"]),
        "w5v_forward_domain_certificate": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="one content-addressed W5 frozen-Q run root")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root), sort_keys=True, separators=(",", ":")))
    except Exception as exc:
        print(f"W5/G5 frozen-Q VERIFY FAIL: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
