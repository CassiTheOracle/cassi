"""Independently replay a sealed W3 periodic-FFT2 transport artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping

import torch

_ARTIFACT_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-artifact.v1"
_MANIFEST_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-manifest.v1"
_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-source-identity.v1"
_REFINEMENT_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-refinement.v1"
_LONG_HORIZON_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-long-horizon.v1"
_ARTIFACT_DOMAIN = "cassi.qi-flow-w3-artifact.v1"
_STAGE_SCHEDULE_SCHEMA = "cassi.qi-flow-g3-stage-schedule.v1"
_RAW_DOMAIN = b"cassi.qi-flow-w3-periodic-fft2.raw.v1"
_RECEIPT_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-verification.v1"
_REPOSITORY = Path(__file__).resolve().parent


class W3VerificationError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise W3VerificationError(message)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> Any:
    def reject_float(_: str) -> None:
        _fail("JSON numeric floats are forbidden; use canonical f64 tags")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs, parse_float=reject_float)
    except W3VerificationError:
        raise
    except Exception as exc:
        _fail(f"cannot parse {path}: {type(exc).__name__}: {exc}")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_object(schema: str, value: Any) -> str:
    schema_bytes = schema.encode("utf-8")
    payload = _canonical(value)
    return hashlib.sha256(len(schema_bytes).to_bytes(8, "big") + schema_bytes + len(payload).to_bytes(8, "big") + payload).hexdigest()


def _f64(value: Any, *, name: str) -> float:
    if not isinstance(value, str) or not value.startswith("f64:") or len(value) != 20:
        _fail(f"{name} is not a canonical f64 tag")
    try:
        number = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    except Exception:
        _fail(f"{name} has invalid f64 payload")
    if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
        _fail(f"{name} is non-finite or negative zero")
    return number


def _close(left: float, right: float, *, tolerance: float = 1.0e-10) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def _raw_hash(raw: bytes, shape: tuple[int, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(len(_RAW_DOMAIN).to_bytes(8, "big"))
    digest.update(_RAW_DOMAIN)
    digest.update(len(shape).to_bytes(8, "big"))
    for dimension in shape:
        digest.update(int(dimension).to_bytes(8, "big"))
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)
    return digest.hexdigest()


def _read_state(root: Path, row: Mapping[str, Any], shape: tuple[int, ...]) -> torch.Tensor:
    if set(row) != {"name", "path", "shape", "bytes", "sha256", "state_sha256"}:
        _fail("runtime state row keyset is not sealed")
    if tuple(row["shape"]) != shape:
        _fail(f"state {row['name']} shape disagrees with runtime layout")
    path = root / row["path"]
    raw = path.read_bytes()
    if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
        _fail(f"state {row['name']} bytes/hash mismatch")
    if _raw_hash(raw, shape) != row["state_sha256"]:
        _fail(f"state {row['name']} domain hash mismatch")
    expected = math.prod(shape) * 8
    if len(raw) != expected:
        _fail(f"state {row['name']} byte count is not float64 layout exact")
    return torch.frombuffer(bytearray(raw), dtype=torch.float64).clone().reshape(shape)


def _signed_frequencies(count: int) -> tuple[int, ...]:
    cutoff = (count - 1) // 2
    return tuple(index if index <= cutoff else index - count for index in range(count))


def _interpolate(values: torch.Tensor, sheet: Mapping[str, Any]) -> torch.Tensor:
    ny, nx = (int(value) for value in sheet["shape_yx"])
    fy, fx = (int(value) for value in sheet["oversampling"]["factors_yx"])
    fine_ny, fine_nx = ny * fy, nx * fx
    source_y = tuple(int(value) for value in sheet["signed_frequency_y"])
    source_x = tuple(int(value) for value in sheet["signed_frequency_x"])
    target_y = {value: index for index, value in enumerate(_signed_frequencies(fine_ny))}
    target_x = {value: index for index, value in enumerate(_signed_frequencies(fine_nx))}
    spectrum = torch.fft.fft2(values, dim=(-3, -2), norm="ortho")
    fine = torch.zeros((fine_ny, fine_nx, values.shape[-1]), dtype=torch.complex128)
    scale = math.sqrt((fine_ny * fine_nx) / (ny * nx))
    for sy, frequency_y in enumerate(source_y):
        for sx, frequency_x in enumerate(source_x):
            fine[target_y[frequency_y], target_x[frequency_x]] = scale * spectrum[sy, sx]
    return torch.fft.ifft2(fine, dim=(-3, -2), norm="ortho")


def _restrict(values: torch.Tensor, sheet: Mapping[str, Any]) -> torch.Tensor:
    ny, nx = (int(value) for value in sheet["shape_yx"])
    fine_ny, fine_nx = values.shape[:2]
    source_y = tuple(int(value) for value in sheet["signed_frequency_y"])
    source_x = tuple(int(value) for value in sheet["signed_frequency_x"])
    fine_y = {value: index for index, value in enumerate(_signed_frequencies(fine_ny))}
    fine_x = {value: index for index, value in enumerate(_signed_frequencies(fine_nx))}
    spectrum = torch.fft.fft2(values, dim=(-3, -2), norm="ortho")
    coarse = torch.zeros((ny, nx, values.shape[-1]), dtype=torch.complex128)
    scale = math.sqrt((ny * nx) / (fine_ny * fine_nx))
    for sy, frequency_y in enumerate(source_y):
        for sx, frequency_x in enumerate(source_x):
            coarse[sy, sx] = scale * spectrum[fine_y[frequency_y], fine_x[frequency_x]]
    return torch.fft.ifft2(coarse, dim=(-3, -2), norm="ortho")


def _spectral_half(position: torch.Tensor, velocity: torch.Tensor, sheet: Mapping[str, Any], *, duration: float, c: float, omega: float, gamma: float) -> tuple[torch.Tensor, torch.Tensor]:
    ny, nx = position.shape[:2]
    ly, lx = (_f64(value, name="sheet extent") for value in sheet["extent_m"])
    frequencies_y = torch.tensor(sheet["signed_frequency_y"], dtype=torch.float64)
    frequencies_x = torch.tensor(sheet["signed_frequency_x"], dtype=torch.float64)
    ky = 2.0 * math.pi * frequencies_y / ly
    kx = 2.0 * math.pi * frequencies_x / lx
    k2 = (ky[:, None].square() + kx[None, :].square()).reshape(-1, 1)
    q0 = torch.fft.fft2(position, dim=(-3, -2), norm="ortho").reshape(ny * nx, -1)
    v0 = torch.fft.fft2(velocity, dim=(-3, -2), norm="ortho").reshape(ny * nx, -1)
    lam = c * c * k2 + omega * omega
    alpha = 0.5 * gamma
    discriminant = lam - alpha * alpha
    tolerance = 64.0 * torch.finfo(torch.float64).eps * torch.maximum(lam.abs(), torch.full_like(lam, max(1.0, alpha * alpha)))
    under = (discriminant > tolerance).reshape(-1)
    over = (discriminant < -tolerance).reshape(-1)
    critical = ~(under | over)
    q1, v1 = torch.empty_like(q0), torch.empty_like(v0)
    decay = math.exp(-alpha * duration)
    if bool(under.any()):
        d = discriminant[under].sqrt()
        cosine, sine_over = torch.cos(d * duration), torch.sin(d * duration) / d
        q, v, lam_u = q0[under], v0[under], lam[under]
        q1[under] = decay * (cosine * q + sine_over * (v + alpha * q))
        v1[under] = decay * (cosine * v - sine_over * (alpha * v + lam_u * q))
    if bool(over.any()):
        d = (-discriminant[over]).sqrt()
        cosine, sine_over = torch.cosh(d * duration), torch.sinh(d * duration) / d
        q, v, lam_o = q0[over], v0[over], lam[over]
        q1[over] = decay * (cosine * q + sine_over * (v + alpha * q))
        v1[over] = decay * (cosine * v - sine_over * (alpha * v + lam_o * q))
    if bool(critical.any()):
        q, v, lam_c = q0[critical], v0[critical], lam[critical]
        q1[critical] = decay * (q + duration * (v + alpha * q))
        v1[critical] = decay * (v - duration * (alpha * v + lam_c * q))
    return (
        torch.fft.ifft2(q1.reshape(ny, nx, -1), dim=(-3, -2), norm="ortho"),
        torch.fft.ifft2(v1.reshape(ny, nx, -1), dim=(-3, -2), norm="ortho"),
    )


def _energy(position: torch.Tensor, velocity: torch.Tensor, sheet: Mapping[str, Any], *, c: float, omega: float, kappa: float, weight: float) -> float:
    ny, nx = position.shape[:2]
    ly, lx = (_f64(value, name="sheet extent") for value in sheet["extent_m"])
    area = _f64(sheet["cell_area_m2"], name="cell area")
    fy = torch.tensor(sheet["signed_frequency_y"], dtype=torch.float64)
    fx = torch.tensor(sheet["signed_frequency_x"], dtype=torch.float64)
    k2 = ((2.0 * math.pi * fy / ly)[:, None].square() + (2.0 * math.pi * fx / lx)[None, :].square()).reshape(ny * nx, 1)
    modes = torch.fft.fft2(position, dim=(-3, -2), norm="ortho").reshape(ny * nx, -1)
    gradient_total = (k2 * modes.abs().square()).sum()
    return float((weight * area * (
        0.5 * velocity.abs().square().sum()
        + 0.5 * c * c * gradient_total
        + 0.5 * omega * omega * position.abs().square().sum()
        + 0.25 * kappa * position.abs().pow(4).sum()
    )).item())


def _advance(field: torch.Tensor, semantic: Mapping[str, Any], duration: float) -> tuple[torch.Tensor, dict[str, float]]:
    layout = semantic["state_layout"]
    scale_count, mode_count = int(layout["scale_count"]), int(layout["mode_count"])
    phi = _f64(semantic["dynamics"]["phi"], name="phi")
    weight = 1.0 / (1.0 + phi * phi)
    dynamics = semantic["dynamics"]
    c_values = [_f64(value, name="c_D") for value in dynamics["c_D_m_per_s"]]
    omega_values = [_f64(value, name="omega_D") for value in dynamics["omega_D_rad_per_s"]]
    gamma_values = [_f64(value, name="gamma_D") for value in dynamics["gamma_D_per_s"]]
    kappa_values = [_f64(value, name="kappa_D") for value in dynamics["kappa_D"]]
    output = field.clone()
    total_before = total_after = damping_work = phase_before = phase_after = phase_expected = 0.0
    for scale, sheet in enumerate(semantic["geometry"]["per_scale"]):
        ny, nx = (int(value) for value in sheet["shape_yx"])
        active = int(sheet["active_site_count"])
        def component(index: int) -> torch.Tensor:
            values = field[scale, index * mode_count : index * mode_count + active]
            return values.reshape(ny, nx, field.shape[-1])
        yang = torch.complex(component(0), component(1))
        yin = torch.complex(component(2), component(3))
        vy = torch.complex(component(4), component(5))
        vi = torch.complex(component(6), component(7))
        d = yang - phi * yin
        coherent = (phi * yang + yin) * weight
        vd = vy - phi * vi
        vc = (phi * vy + vi) * weight
        c, omega, gamma, kappa = c_values[scale], omega_values[scale], gamma_values[scale], kappa_values[scale]
        before = _energy(d, vd, sheet, c=c, omega=omega, kappa=kappa, weight=weight)
        phase0 = float((weight * torch.imag(torch.conj(d) * vd).sum() * _f64(sheet["cell_area_m2"], name="cell area")).item())
        half = 0.5 * duration
        if half and kappa:
            high = _interpolate(d, sheet)
            vd = vd - half * kappa * _restrict(high.abs().square() * high, sheet)
        linear_before = _energy(d, vd, sheet, c=c, omega=omega, kappa=0.0, weight=weight)
        d, vd = _spectral_half(d, vd, sheet, duration=half, c=c, omega=omega, gamma=gamma)
        linear_middle = _energy(d, vd, sheet, c=c, omega=omega, kappa=0.0, weight=weight)
        damping = linear_middle - linear_before
        linear_before_2 = linear_middle
        d, vd = _spectral_half(d, vd, sheet, duration=half, c=c, omega=omega, gamma=gamma)
        linear_after_2 = _energy(d, vd, sheet, c=c, omega=omega, kappa=0.0, weight=weight)
        damping += linear_after_2 - linear_before_2
        if half and kappa:
            high = _interpolate(d, sheet)
            vd = vd - half * kappa * _restrict(high.abs().square() * high, sheet)
        after = _energy(d, vd, sheet, c=c, omega=omega, kappa=kappa, weight=weight)
        next_yang = weight * d + phi * coherent
        next_yin = coherent - phi * weight * d
        next_vy = weight * vd + phi * vc
        next_vi = vc - phi * weight * vd
        for index, values in ((0, next_yang.real), (1, next_yang.imag), (2, next_yin.real), (3, next_yin.imag), (4, next_vy.real), (5, next_vy.imag), (6, next_vi.real), (7, next_vi.imag)):
            start = index * mode_count
            output[scale, start : start + mode_count].zero_()
            output[scale, start : start + active] = values.reshape(active, -1)
        total_before += before
        total_after += after
        damping_work += damping
        phase1 = float((weight * torch.imag(torch.conj(d) * vd).sum() * _f64(sheet["cell_area_m2"], name="cell area")).item())
        phase_before += phase0
        phase_after += phase1
        phase_expected += math.exp(-gamma * duration) * phase0
    return output.contiguous(), {
        "pre_energy": total_before,
        "post_energy": total_after,
        "damping_work": damping_work,
        "transport_closure": total_after - total_before - damping_work,
        "phase_charge_before": phase_before,
        "phase_charge_after": phase_after,
        "phase_charge_expected": phase_expected,
        "phase_continuity_residual": phase_after - phase_expected,
    }


def _scalar_half(q: complex, v: complex, *, duration: float, c: float, omega: float, gamma: float) -> tuple[complex, complex]:
    lam, alpha = omega * omega, 0.5 * gamma
    discriminant = lam - alpha * alpha
    decay = math.exp(-alpha * duration)
    tolerance = 64.0 * 2.220446049250313e-16 * max(abs(lam), 1.0, alpha * alpha)
    if discriminant > tolerance:
        d = math.sqrt(discriminant); cosine, sine_over = math.cos(d * duration), math.sin(d * duration) / d
    elif discriminant < -tolerance:
        d = math.sqrt(-discriminant); cosine, sine_over = math.cosh(d * duration), math.sinh(d * duration) / d
    else:
        cosine, sine_over = 1.0, duration
    return decay * (cosine * q + sine_over * (v + alpha * q)), decay * (cosine * v - sine_over * (alpha * v + lam * q))


def _scalar_split(q: complex, v: complex, *, h: float, c: float, omega: float, gamma: float, kappa: float) -> tuple[complex, complex]:
    v -= 0.5 * h * kappa * abs(q) ** 2 * q
    q, v = _scalar_half(q, v, duration=0.5 * h, c=c, omega=omega, gamma=gamma)
    q, v = _scalar_half(q, v, duration=0.5 * h, c=c, omega=omega, gamma=gamma)
    v -= 0.5 * h * kappa * abs(q) ** 2 * q
    return q, v


def _verify_long_horizon(payload: Mapping[str, Any], semantic: Mapping[str, Any]) -> None:
    if payload.get("schema") != _LONG_HORIZON_SCHEMA or payload.get("status") != "PASS":
        _fail("long-horizon receipt header is invalid")
    h = _f64(payload["step_s"], name="long-horizon step")
    steps = int(payload["steps"])
    dynamics = semantic["dynamics"]
    arrays = {
        "c": [_f64(value, name="c") for value in dynamics["c_D_m_per_s"]],
        "omega": [_f64(value, name="omega") for value in dynamics["omega_D_rad_per_s"]],
        "gamma": [_f64(value, name="gamma") for value in dynamics["gamma_D_per_s"]],
        "kappa": [_f64(value, name="kappa") for value in dynamics["kappa_D"]],
    }
    phi = _f64(dynamics["phi"], name="phi")
    weight = 1.0 / (1.0 + phi * phi)
    coherence = complex(0.01, -0.02)
    coherence_velocity = complex(-0.01, 0.015)
    amplitude_cap = _f64(payload["candidate_amplitude_cap"], name="candidate amplitude cap")

    def raw_component_max(q: complex, v: complex) -> float:
        values = (
            weight * q + phi * coherence,
            coherence - phi * weight * q,
            weight * v + phi * coherence_velocity,
            coherence_velocity - phi * weight * v,
        )
        return max(max(abs(value.real), abs(value.imag)) for value in values)
    if steps != int(math.ceil(8.0 * max(2.0 * math.pi / value for value in arrays["omega"]) / h)):
        _fail("long-horizon stopping rule mismatch")
    if len(payload["rows"]) != len(arrays["c"]):
        _fail("long-horizon scale row count mismatch")
    for scale, row in enumerate(payload["rows"]):
        q, v = complex(0.20, 0.07), complex(0.04, -0.03)
        initial = 0.5 * abs(v) ** 2 + 0.5 * arrays["omega"][scale] ** 2 * abs(q) ** 2 + 0.25 * arrays["kappa"][scale] * abs(q) ** 4
        maximum_energy, maximum_amplitude = initial, abs(q)
        maximum_raw_component = raw_component_max(q, v)
        for _ in range(steps):
            q, v = _scalar_split(q, v, h=h, c=arrays["c"][scale], omega=arrays["omega"][scale], gamma=arrays["gamma"][scale], kappa=arrays["kappa"][scale])
            energy = 0.5 * abs(v) ** 2 + 0.5 * arrays["omega"][scale] ** 2 * abs(q) ** 2 + 0.25 * arrays["kappa"][scale] * abs(q) ** 4
            maximum_energy, maximum_amplitude = max(maximum_energy, energy), max(maximum_amplitude, abs(q), abs(v))
            maximum_raw_component = max(maximum_raw_component, raw_component_max(q, v))
        checks = (
            (initial, _f64(row["initial_energy"], name="initial energy")),
            (energy, _f64(row["final_energy"], name="final energy")),
            (maximum_energy, _f64(row["maximum_energy"], name="maximum energy")),
            (maximum_amplitude, _f64(row["maximum_amplitude"], name="maximum amplitude")),
            (maximum_raw_component, _f64(row["maximum_raw_component"], name="maximum raw component")),
            (q.real, _f64(row["final_q"][0], name="final q real")),
            (q.imag, _f64(row["final_q"][1], name="final q imag")),
            (v.real, _f64(row["final_v"][0], name="final v real")),
            (v.imag, _f64(row["final_v"][1], name="final v imag")),
        )
        if any(not _close(left, right, tolerance=1.0e-12) for left, right in checks):
            _fail(f"long-horizon replay mismatch at scale {scale}")
        if maximum_raw_component > amplitude_cap:
            _fail(f"long-horizon raw component cap exceeded at scale {scale}")
def _verify_stage_schedule(payload: Mapping[str, Any], semantic: Mapping[str, Any]) -> str:
    if set(payload) != {"schema", "h_s", "substeps", "stages", "stage_schedule_sha256"}:
        _fail("W3 stage schedule keyset mismatch")
    if payload.get("schema") != _STAGE_SCHEDULE_SCHEMA or payload.get("substeps") != 7:
        _fail("W3 stage schedule header mismatch")
    schedule_core = {key: value for key, value in payload.items() if key != "stage_schedule_sha256"}
    schedule_sha256 = _hash_object(_STAGE_SCHEDULE_SCHEMA, schedule_core)
    if payload.get("stage_schedule_sha256") != schedule_sha256:
        _fail("W3 stage schedule canonical hash mismatch")
    h = _f64(payload["h_s"], name="stage schedule h")
    if h != _f64(semantic["dynamics"]["h_min_s"], name="semantic h_min"):
        _fail("W3 stage schedule duration is not the frozen release step")
    specs = (
        ("preflight", 0.0, ("predecessor_raw", "source_request"), ("preflight_receipt",), (), "active"),
        ("first_local_force_velocity_half_kick", 0.5, ("D_0", "V_D_0"), ("V_D_1",), ("preflight",), "active"),
        ("first_analytic_damped_spectral_half_propagation", 0.5, ("D_0", "V_D_1"), ("D_2", "V_D_2"), ("first_local_force_velocity_half_kick",), "active"),
        ("centered_conversion_placeholder", 1.0, ("D_2", "V_D_2"), ("conversion_placeholder",), ("first_analytic_damped_spectral_half_propagation",), "inactive-w3"),
        ("second_analytic_damped_spectral_half_propagation", 0.5, ("D_2", "V_D_2"), ("D_3", "V_D_3"), ("centered_conversion_placeholder",), "active"),
        ("second_local_force_velocity_half_kick", 0.5, ("D_3", "V_D_3"), ("V_D_4",), ("second_analytic_damped_spectral_half_propagation",), "active"),
        ("precommit", 0.0, ("D_3", "V_D_4"), ("candidate_raw", "diagnostics", "commit_decision"), ("second_local_force_velocity_half_kick",), "active"),
    )
    stages = payload.get("stages")
    if not isinstance(stages, list) or len(stages) != len(specs):
        _fail("W3 seven-stage schedule is absent")
    row_keys = {"ordinal", "name", "duration_s", "reads", "writes", "dependencies", "mode"}
    for ordinal, (row, spec) in enumerate(zip(stages, specs), start=1):
        name, duration_factor, reads, writes, dependencies, mode = spec
        if (
            not isinstance(row, Mapping)
            or set(row) != row_keys
            or row.get("ordinal") != ordinal
            or row.get("name") != name
            or _f64(row.get("duration_s"), name=f"stage {ordinal} duration") != h * duration_factor
            or row.get("reads") != list(reads)
            or row.get("writes") != list(writes)
            or row.get("dependencies") != list(dependencies)
            or row.get("mode") != mode
        ):
            _fail(f"W3 stage {ordinal} does not match the frozen split schedule")
    return schedule_sha256




def verify_artifact(path: str | Path) -> dict[str, Any]:
    root = Path(path).resolve()
    index = _load(root / "index.json")
    if index.get("schema") != _ARTIFACT_SCHEMA or index.get("status") != "PASS_W3_G3":
        _fail("W3 index header is invalid")
    self_sha = index.get("self_sha256")
    without_self = {key: value for key, value in index.items() if key != "self_sha256"}
    if self_sha != _hash_object(_ARTIFACT_SCHEMA, without_self):
        _fail("W3 index self hash mismatch")
    run_id = index.get("run_id")
    core = {key: value for key, value in without_self.items() if key != "run_id"}
    if run_id != _hash_object(_ARTIFACT_DOMAIN, core):
        _fail("W3 content-addressed run id mismatch")

    object_rows = index.get("objects")
    if not isinstance(object_rows, list):
        _fail("W3 object index is absent")
    indexed_paths = [row.get("path") for row in object_rows]
    if indexed_paths != sorted(indexed_paths, key=lambda value: value.encode("utf-8")) or len(set(indexed_paths)) != len(indexed_paths):
        _fail("W3 objects are not unique UTF-8 byte ordered")
    actual_paths = sorted((item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file() and item.name != "index.json"), key=lambda value: value.encode("utf-8"))
    if indexed_paths != actual_paths:
        _fail("W3 object keyset is not exact")
    for row in object_rows:
        if set(row) != {"path", "bytes", "sha256"}:
            _fail("W3 object row keyset is not sealed")
        raw = (root / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
            _fail(f"W3 object mismatch: {row['path']}")

    manifest = _load(root / "manifest.json")
    if manifest.get("schema") != _MANIFEST_SCHEMA:
        _fail("W3 manifest schema mismatch")
    manifest_hash = manifest.get("manifest_sha256")
    manifest_core = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest_hash != _hash_object(_MANIFEST_SCHEMA, manifest_core) or manifest_hash != index.get("manifest_sha256"):
        _fail("W3 manifest hash mismatch")

    source_identity = _load(root / "run-spec" / "source-identity.json")
    if source_identity.get("schema") != _SOURCE_IDENTITY_SCHEMA:
        _fail("W3 source identity schema mismatch")
    source_hash = source_identity.get("source_identity_sha256")
    source_core = {key: value for key, value in source_identity.items() if key != "source_identity_sha256"}
    if source_hash != _hash_object(_SOURCE_IDENTITY_SCHEMA, source_core) or source_hash != index.get("source_identity_sha256"):
        _fail("W3 source identity hash mismatch")
    for row in source_identity.get("sources", []):
        relative = row.get("path")
        snapshot = (root / "run-spec" / "sources" / relative).read_bytes()
        live = (_REPOSITORY / relative).read_bytes()
        if len(snapshot) != row.get("bytes") or _sha(snapshot) != row.get("sha256") or snapshot != live:
            _fail(f"W3 source snapshot is not current and exact: {relative}")

    parent = _load(root / "run-spec" / "w2-parent.json")
    parent_path = _REPOSITORY / parent["path"]
    from verify_cassi_qi_geometry import verify_artifact as verify_w2_artifact
    parent_receipt = verify_w2_artifact(parent_path)
    if parent_receipt.get("status") != "PASS_W2_G2" or parent_path.name != index.get("parent_w2_run_id"):
        _fail("W3 parent W2 verification failed")

    profile = _load(root / "run-spec" / "w3-profile.json")
    semantic = profile.get("semantic")
    if not isinstance(semantic, Mapping) or profile.get("profile_sha256") != index.get("profile_sha256"):
        _fail("W3 profile linkage mismatch")
    semantic_hash = _hash_object(semantic.get("schema"), semantic)
    registry = profile.get("schema_registry")
    if not isinstance(registry, Mapping):
        _fail("W3 schema registry is absent")
    registry_hash = _hash_object(registry.get("schema"), registry)
    contract_root = profile.get("contract_root")
    if not isinstance(contract_root, Mapping):
        _fail("W3 contract root is absent")
    contract_root_core = {
        key: value for key, value in contract_root.items() if key != "self_sha256"
    }
    contract_root_hash = _hash_object(contract_root.get("schema"), contract_root_core)
    profile_core = {
        key: value for key, value in profile.items() if key != "profile_sha256"
    }
    profile_hash = _hash_object(profile.get("schema"), profile_core)
    if (
        semantic_hash != profile.get("semantic_sha256")
        or registry_hash != profile.get("schema_registry_sha256")
        or contract_root_hash != contract_root.get("self_sha256")
        or contract_root_hash != profile.get("contract_root_sha256")
        or profile_hash != profile.get("profile_sha256")
    ):
        _fail("W3 profile canonical hashes do not replay")
    if profile.get("contract_root_sha256") != index.get("contract_root_sha256") or profile.get("semantic_sha256") != index.get("semantic_sha256"):
        _fail("W3 profile root/semantic linkage mismatch")
    if profile.get("base_geometry_profile_sha256") != index.get("parent_w2_profile_sha256") or profile.get("base_geometry_contract_root_sha256") != index.get("parent_w2_contract_root_sha256"):
        _fail("W3 profile does not descend from sealed W2")
    stage_schedule = _load(root / "run-spec" / "w3-stage-schedule.json")
    stage_schedule_sha256 = _verify_stage_schedule(stage_schedule, semantic)
    if stage_schedule_sha256 != index.get("stage_schedule_sha256"):
        _fail("W3 seven-stage schedule linkage mismatch")

    runtime = _load(root / "results" / "runtime.json")
    runtime_layout = runtime["state_layout"]
    shape = tuple(int(value) for value in runtime_layout["shape"])
    expected_shape = (
        int(semantic["state_layout"]["scale_count"]),
        int(semantic["state_layout"]["component_count"]) * int(semantic["state_layout"]["mode_count"]),
        1,
    )
    if (
        shape != expected_shape
        or runtime_layout.get("dtype") != semantic["state_layout"]["dtype"]
        or runtime_layout.get("endianness") != semantic["state_layout"]["endianness"]
    ):
        _fail("W3 runtime state layout mismatch")
    states = {row["name"]: _read_state(root, row, shape) for row in runtime["states"]}
    h = _f64(runtime["duration_s"], name="runtime duration")
    maximum_error = 0.0
    for prefix, duration in (("seeded", h), ("conjugate", h), ("zero", 0.0)):
        replay, diagnostics = _advance(states[f"{prefix}-predecessor"], semantic, duration)
        error = float((replay - states[f"{prefix}-candidate"]).abs().amax().item())
        maximum_error = max(maximum_error, error)
        if error > 1.0e-10:
            _fail(f"W3 independent replay mismatch for {prefix}: {error}")
        if prefix == "seeded":
            recorded = runtime["seeded_diagnostics"]
            for key in ("pre_energy", "post_energy", "damping_work", "transport_closure", "phase_charge_before", "phase_charge_after", "phase_charge_expected", "phase_continuity_residual"):
                if not _close(diagnostics[key], _f64(recorded[key], name=f"recorded {key}"), tolerance=1.0e-10):
                    _fail(f"W3 independent diagnostic mismatch: {key}")
            if diagnostics["damping_work"] > 1.0e-15:
                _fail("W3 damping work is not dissipative")
    if not torch.equal(states["zero-predecessor"], states["zero-candidate"]):
        _fail("W3 zero state is not exact")
    conjugate_expected = states["seeded-candidate"].clone()
    mode_count = int(semantic["state_layout"]["mode_count"])
    for component in (1, 3, 5, 7):
        conjugate_expected[:, component * mode_count : (component + 1) * mode_count].neg_()
    conjugation_error = float((conjugate_expected - states["conjugate-candidate"]).abs().amax().item())
    maximum_error = max(maximum_error, conjugation_error)
    if conjugation_error > 1.0e-10:
        _fail("W3 phase-conjugation equivariance failed")

    refinement = _load(root / "results" / "refinement.json")
    if refinement.get("schema") != _REFINEMENT_SCHEMA or refinement.get("status") != "PASS":
        _fail("W3 refinement receipt header is invalid")
    refinement_h = _f64(refinement["duration_s"], name="refinement duration")
    predecessor = states["refinement-predecessor"]
    full, _ = _advance(predecessor, semantic, refinement_h)
    half, _ = _advance(predecessor, semantic, 0.5 * refinement_h)
    halves, _ = _advance(half, semantic, 0.5 * refinement_h)
    quarter = predecessor
    for _ in range(4):
        quarter, _ = _advance(quarter, semantic, 0.25 * refinement_h)
    for name, replay in (("refinement-full", full), ("refinement-halves", halves), ("refinement-quarters", quarter)):
        error = float((replay - states[name]).abs().amax().item())
        maximum_error = max(maximum_error, error)
        if error > 1.0e-10:
            _fail(f"W3 refinement state replay mismatch: {name}")
    coarse_error = float((full - halves).abs().amax().item())
    fine_error = float((halves - quarter).abs().amax().item())
    ratio = coarse_error / fine_error if fine_error > 0.0 else math.inf
    if not (_close(coarse_error, _f64(refinement["coarse_error"], name="coarse error"), tolerance=1.0e-9) and _close(fine_error, _f64(refinement["fine_error"], name="fine error"), tolerance=1.0e-9) and _close(ratio, _f64(refinement["ratio"], name="refinement ratio"), tolerance=1.0e-8) and ratio >= 3.0):
        _fail("W3 refinement replay/order mismatch")

    controls = _load(root / "results" / "controls.json")
    if controls.get("status") != "PASS" or controls.get("zero_state_exact") is not True or controls.get("source_rejected") is not True or controls.get("inactive_tail_nonzero") != 0:
        _fail("W3 control receipt failed")
    _verify_long_horizon(_load(root / "results" / "long-horizon.json"), semantic)

    receipt_core = {
        "schema": _RECEIPT_SCHEMA,
        "status": "PASS_W3_G3",
        "run_id": run_id,
        "profile_sha256": index["profile_sha256"],
        "contract_root_sha256": index["contract_root_sha256"],
        "source_identity_sha256": source_hash,
        "parent_w2_run_id": index["parent_w2_run_id"],
        "maximum_numeric_error": "f64:" + struct.pack(">d", maximum_error).hex(),
    }
    return {**receipt_core, "self_sha256": _hash_object(_RECEIPT_SCHEMA, receipt_core)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(verify_artifact(args.artifact), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
