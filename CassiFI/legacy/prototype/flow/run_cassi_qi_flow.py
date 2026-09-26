"""Seal the corrected W3 periodic-FFT2 transport evidence artifact."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Mapping

import torch

from cassi_qi_field import QiFlowStateV3, transition_v3_transport
from cassi_qi_geometry import PeriodicSheetGeometry, load_w2_geometry_profile
from cassi_qi_profile import canonical_json_bytes, load_development_profile
from cassi_qi_transport import (
    W3_ARTIFACT_DOMAIN,
    W3_G3_STAGE_SCHEDULE,
    W3_H_S,
    W3_RUN_INDEX_SCHEMA,
    W3_STAGE_SCHEDULE_SCHEMA,
    load_w3_transport_profile,
)
from verify_cassi_qi_geometry import verify_artifact as verify_w2_artifact

_REPOSITORY = Path(__file__).resolve().parent
_W2_ROOT = _REPOSITORY / "_diag" / "cassi-qi-flow-w2-periodic-fft2-final"
_W3_ROOT = _REPOSITORY / "_diag" / "cassi-qi-flow-w3-periodic-fft2-final"
_ARTIFACT_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-artifact.v1"
_MANIFEST_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-manifest.v1"
_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-source-identity.v1"
_RUNTIME_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-runtime.v1"
_REFINEMENT_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-refinement.v1"
_LONG_HORIZON_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-long-horizon.v1"
_CONTROLS_SCHEMA = "cassi.qi-flow-w3-periodic-fft2-controls.v1"
_RAW_DOMAIN = b"cassi.qi-flow-w3-periodic-fft2.raw.v1"
_SOURCE_PATHS = (
    "CassiFI/01-field-physics.md",
    "CassiFI/04-execution-contract.md",
    "CassiFI/10-work-packages.md",
    "CassiFI/11-validation-gates.md",
    "cassi-qi-flow-development.json",
    "cassi_qi_profile.py",
    "cassi_qi_geometry.py",
    "verify_cassi_qi_geometry.py",
    "cassi_qi_transport.py",
    "cassi_qi_field.py",
    "run_cassi_qi_flow.py",
    "verify_cassi_qi_transport.py",
    "test_cassi_qi_transport.py",
    "test_verify_cassi_qi_transport.py",
)


class W3ArtifactError(RuntimeError):
    pass


def _plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _f64(value: float) -> str:
    number = float(value)
    if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
        raise W3ArtifactError("artifact numbers must be finite without negative zero")
    return "f64:" + struct.pack(">d", number).hex()


def _tag_numbers(value: Any) -> Any:
    if isinstance(value, float):
        return _f64(value)
    if isinstance(value, Mapping):
        return {str(key): _tag_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_tag_numbers(item) for item in value]
    return value


def _canonical(value: Any) -> bytes:
    return canonical_json_bytes(_tag_numbers(_plain(value)))


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_object(schema: str, value: Any) -> str:
    schema_bytes = schema.encode("utf-8")
    payload = _canonical(value)
    return hashlib.sha256(
        len(schema_bytes).to_bytes(8, "big")
        + schema_bytes
        + len(payload).to_bytes(8, "big")
        + payload
    ).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value) + b"\n")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _state_raw(state: QiFlowStateV3) -> bytes:
    tensor = state.field.detach().cpu().contiguous()
    if tensor.dtype != torch.float64:
        raise W3ArtifactError("W3 artifacts require float64 state")
    return tensor.numpy().astype("<f8", copy=False).tobytes(order="C")


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


def _discover_w2(profile: Any) -> tuple[Path, Mapping[str, Any]]:
    if not _W2_ROOT.is_dir():
        raise W3ArtifactError("the current W2 periodic-FFT2 artifact root is absent")
    matches: list[tuple[Path, Mapping[str, Any]]] = []
    for child in sorted((path for path in _W2_ROOT.iterdir() if path.is_dir()), key=lambda path: path.name.encode("utf-8")):
        try:
            receipt = verify_w2_artifact(child)
            index = _load_json(child / "index.json")
        except Exception:
            continue
        if (
            receipt.get("status") == "PASS_W2_G2"
            and index.get("profile_sha256") == profile.profile_sha256
            and index.get("contract_root_sha256") == profile.contract_root_sha256
        ):
            matches.append((child, receipt))
    if len(matches) != 1:
        raise W3ArtifactError(f"expected one source-exact current W2 parent, found {len(matches)}")
    return matches[0]


def _set_component(field: torch.Tensor, surface: PeriodicSheetGeometry, scale: int, component: int, grid: torch.Tensor) -> torch.Tensor:
    return surface.scatter_active(grid.contiguous(), scale=scale, component=component, state=field)


def _state_fixture(base: Any, surface: PeriodicSheetGeometry, *, kind: str) -> QiFlowStateV3:
    field = QiFlowStateV3.create(base, batch_lanes=1).field
    phi = float.fromhex("0x1.9e3779b97f4a8p+0")
    weight_d = 1.0 / (1.0 + phi * phi)
    for scale in range(surface.profile.scale_count):
        ny, nx = surface.sheet_shape(scale)
        y, x = surface.coordinate_mesh(scale)
        dy, dx = surface.spacing_m(scale)
        ly, lx = ny * dy, nx * dx
        if kind == "seeded":
            phase = 2.0 * math.pi * ((scale % 2 + 1) * x / lx + y / ly)
            differential = (2.0e-5 + scale * 2.5e-6) * torch.exp(1.0j * phase)
            differential_velocity = (1.0e-3 + scale * 1.0e-4) * torch.exp(1.0j * (phase + 0.37))
            coherence = 1.0e-4 * torch.exp(-1.0j * (phase * 0.5 + 0.11))
            coherence_velocity = 2.0e-4 * torch.exp(1.0j * (phase * 0.25 - 0.23))
            epsilon = (1.0e-8 * (1.5 + 0.25 * torch.cos(phase))).to(torch.float64)
        elif kind == "constant":
            differential = torch.full((ny, nx), complex(0.20, 0.07), dtype=torch.complex128)
            differential_velocity = torch.full((ny, nx), complex(0.04, -0.03), dtype=torch.complex128)
            coherence = torch.full((ny, nx), complex(0.01, -0.02), dtype=torch.complex128)
            coherence_velocity = torch.full((ny, nx), complex(-0.01, 0.015), dtype=torch.complex128)
            epsilon = torch.full((ny, nx), 1.0e-8, dtype=torch.float64)
        elif kind == "zero":
            differential = torch.zeros((ny, nx), dtype=torch.complex128)
            differential_velocity = torch.zeros_like(differential)
            coherence = torch.zeros_like(differential)
            coherence_velocity = torch.zeros_like(differential)
            epsilon = torch.zeros((ny, nx), dtype=torch.float64)
        else:
            raise W3ArtifactError(f"unknown fixture kind {kind!r}")
        yang = weight_d * differential + phi * coherence
        yin = coherence - phi * weight_d * differential
        velocity_yang = weight_d * differential_velocity + phi * coherence_velocity
        velocity_yin = coherence_velocity - phi * weight_d * differential_velocity
        for component, values in (
            (0, yang.real), (1, yang.imag), (2, yin.real), (3, yin.imag),
            (4, velocity_yang.real), (5, velocity_yang.imag),
            (6, velocity_yin.real), (7, velocity_yin.imag), (8, epsilon),
        ):
            field = _set_component(field, surface, scale, component, values[..., None])
    state = QiFlowStateV3(field.contiguous())
    state.validate(base)
    return state


def _conjugate(state: QiFlowStateV3) -> QiFlowStateV3:
    field = state.field.clone()
    mode_count = field.shape[1] // 9
    for component in (1, 3, 5, 7):
        field[:, component * mode_count : (component + 1) * mode_count].neg_()
    return QiFlowStateV3(field.contiguous())


def _step(state: QiFlowStateV3, geometry: Any, transport: Any, duration: float) -> Any:
    result = transition_v3_transport(
        state,
        geometry_profile=geometry,
        transport_profile=transport,
        duration_s=duration,
    )
    if not result.committable or result.candidate is None or result.diagnostics is None or result.ledger is None:
        raise W3ArtifactError(f"W3 fixture was rejected: {result.failure_reason}")
    return result


def _refinement(state: QiFlowStateV3, geometry: Any, transport: Any, h: float) -> tuple[dict[str, Any], dict[str, QiFlowStateV3]]:
    full = _step(state, geometry, transport, h).candidate
    half = _step(state, geometry, transport, 0.5 * h).candidate
    halves = _step(half, geometry, transport, 0.5 * h).candidate
    quarter = state
    for _ in range(4):
        quarter = _step(quarter, geometry, transport, 0.25 * h).candidate
    error_h = float((full.field - halves.field).abs().amax().item())
    error_half = float((halves.field - quarter.field).abs().amax().item())
    ratio = error_h / error_half if error_half > 0.0 else math.inf
    if not (math.isfinite(ratio) and ratio >= 3.0):
        raise W3ArtifactError(f"W3 refinement ratio {ratio!r} does not demonstrate second order")
    return (
        {
            "schema": _REFINEMENT_SCHEMA,
            "duration_s": h,
            "coarse_error": error_h,
            "fine_error": error_half,
            "ratio": ratio,
            "threshold": 3.0,
            "status": "PASS",
        },
        {"predecessor": state, "full": full, "halves": halves, "quarters": quarter},
    )


def _scalar_half(q: complex, v: complex, *, duration: float, c: float, omega: float, gamma: float, k2: float = 0.0) -> tuple[complex, complex]:
    lam = c * c * k2 + omega * omega
    alpha = 0.5 * gamma
    discriminant = lam - alpha * alpha
    decay = math.exp(-alpha * duration)
    tolerance = 64.0 * 2.220446049250313e-16 * max(abs(lam), 1.0, alpha * alpha)
    if discriminant > tolerance:
        d = math.sqrt(discriminant)
        cosine, sine_over = math.cos(d * duration), math.sin(d * duration) / d
    elif discriminant < -tolerance:
        d = math.sqrt(-discriminant)
        cosine, sine_over = math.cosh(d * duration), math.sinh(d * duration) / d
    else:
        cosine, sine_over = 1.0, duration
    return (
        decay * (cosine * q + sine_over * (v + alpha * q)),
        decay * (cosine * v - sine_over * (alpha * v + lam * q)),
    )


def _scalar_split(q: complex, v: complex, *, h: float, c: float, omega: float, gamma: float, kappa: float) -> tuple[complex, complex]:
    v -= 0.5 * h * kappa * abs(q) ** 2 * q
    q, v = _scalar_half(q, v, duration=0.5 * h, c=c, omega=omega, gamma=gamma)
    q, v = _scalar_half(q, v, duration=0.5 * h, c=c, omega=omega, gamma=gamma)
    v -= 0.5 * h * kappa * abs(q) ** 2 * q
    return q, v


def _long_horizon(profile: Any) -> dict[str, Any]:
    parameters = profile.pinned_parameters
    h = parameters.h_max_s
    periods = [2.0 * math.pi / value for value in parameters.omega_rad_per_s]
    duration = 8.0 * max(periods)
    steps = int(math.ceil(duration / h))
    rows: list[dict[str, Any]] = []
    phi = parameters.phi
    weight = 1.0 / (1.0 + phi * phi)
    coherence = complex(0.01, -0.02)
    coherence_velocity = complex(-0.01, 0.015)

    def raw_component_max(q: complex, v: complex) -> float:
        values = (
            weight * q + phi * coherence,
            coherence - phi * weight * q,
            weight * v + phi * coherence_velocity,
            coherence_velocity - phi * weight * v,
        )
        return max(max(abs(value.real), abs(value.imag)) for value in values)

    for scale, (c, omega, gamma, kappa) in enumerate(zip(
        parameters.c_D_m_per_s,
        parameters.omega_rad_per_s,
        parameters.gamma_per_s,
        parameters.kappa,
    )):
        q, v = complex(0.20, 0.07), complex(0.04, -0.03)
        initial_energy = 0.5 * abs(v) ** 2 + 0.5 * omega * omega * abs(q) ** 2 + 0.25 * kappa * abs(q) ** 4
        maximum_energy = initial_energy
        maximum_amplitude = abs(q)
        maximum_raw_component = raw_component_max(q, v)
        for _ in range(steps):
            q, v = _scalar_split(q, v, h=h, c=c, omega=omega, gamma=gamma, kappa=kappa)
            energy = 0.5 * abs(v) ** 2 + 0.5 * omega * omega * abs(q) ** 2 + 0.25 * kappa * abs(q) ** 4
            maximum_energy = max(maximum_energy, energy)
            maximum_amplitude = max(maximum_amplitude, abs(q), abs(v))
            maximum_raw_component = max(maximum_raw_component, raw_component_max(q, v))
            if not all(math.isfinite(value) for value in (q.real, q.imag, v.real, v.imag, energy)):
                raise W3ArtifactError("W3 long-horizon constant-mode trial became non-finite")
        rows.append({
            "scale": scale,
            "initial_energy": initial_energy,
            "final_energy": energy,
            "maximum_energy": maximum_energy,
            "maximum_amplitude": maximum_amplitude,
            "maximum_raw_component": maximum_raw_component,
            "final_q": [q.real, q.imag],
            "final_v": [v.real, v.imag],
        })
        if maximum_raw_component > parameters.amplitude_cap:
            raise W3ArtifactError("W3 long-horizon trial exceeded the raw component cap")
    return {
        "schema": _LONG_HORIZON_SCHEMA,
        "fixture": "constant-periodic-mode-invariant-subspace",
        "periods": 8,
        "step_s": h,
        "steps": steps,
        "duration_s": steps * h,
        "candidate_amplitude_cap": parameters.amplitude_cap,
        "rows": rows,
        "finite": True,
        "status": "PASS",
    }


def _source_identity(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in _SOURCE_PATHS:
        source = _REPOSITORY / relative
        if not source.is_file():
            raise W3ArtifactError(f"required W3 source is absent: {relative}")
        raw = source.read_bytes()
        snapshot = root / "run-spec" / "sources" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        rows.append({"path": relative, "bytes": len(raw), "sha256": _hash_bytes(raw)})
    rows.sort(key=lambda row: row["path"].encode("utf-8"))
    payload = {"schema": _SOURCE_IDENTITY_SCHEMA, "sources": rows}
    payload["source_identity_sha256"] = _hash_object(_SOURCE_IDENTITY_SCHEMA, payload)
    return payload


def _object_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((item for item in root.rglob("*") if item.is_file() and item.name != "index.json"), key=lambda item: item.relative_to(root).as_posix().encode("utf-8")):
        raw = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": _hash_bytes(raw)})
    return rows


def run(*, output_root: str | Path | None = None) -> dict[str, Any]:
    base = load_development_profile()
    geometry = load_w2_geometry_profile(base_profile=base)
    surface = PeriodicSheetGeometry(geometry)
    transport = load_w3_transport_profile(base_profile=base, geometry_profile=geometry)
    parent_path, parent_verification = _discover_w2(geometry)
    root = Path(output_root).resolve() if output_root is not None else _W3_ROOT
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".w3-", dir=root))
    try:
        source_identity = _source_identity(temporary)
        profile_payload = _plain(transport.payload)
        stage_schedule = _plain(W3_G3_STAGE_SCHEDULE)
        stage_schedule_sha256 = _hash_object(W3_STAGE_SCHEDULE_SCHEMA, stage_schedule)
        stage_schedule["stage_schedule_sha256"] = stage_schedule_sha256
        _write_json(temporary / "run-spec" / "w3-profile.json", profile_payload)
        _write_json(temporary / "run-spec" / "w3-stage-schedule.json", stage_schedule)
        _write_json(temporary / "run-spec" / "source-identity.json", source_identity)
        parent_payload = {
            "path": parent_path.relative_to(_REPOSITORY).as_posix(),
            "run_id": parent_path.name,
            "verification": _plain(parent_verification),
        }
        _write_json(temporary / "run-spec" / "w2-parent.json", parent_payload)

        duration = transport.pinned_parameters.h
        seeded = _state_fixture(base, surface, kind="seeded")
        seeded_step = _step(seeded, geometry, transport, duration)
        conjugate = _conjugate(seeded)
        conjugate_step = _step(conjugate, geometry, transport, duration)
        zero = _state_fixture(base, surface, kind="zero")
        zero_step = _step(zero, geometry, transport, 0.0)
        constant = _state_fixture(base, surface, kind="constant")
        refinement, refinement_states = _refinement(
            constant,
            geometry,
            transport,
            transport.pinned_parameters.h_max_s,
        )
        raw_states = {
            "seeded-predecessor": seeded,
            "seeded-candidate": seeded_step.candidate,
            "conjugate-predecessor": conjugate,
            "conjugate-candidate": conjugate_step.candidate,
            "zero-predecessor": zero,
            "zero-candidate": zero_step.candidate,
            "refinement-predecessor": refinement_states["predecessor"],
            "refinement-full": refinement_states["full"],
            "refinement-halves": refinement_states["halves"],
            "refinement-quarters": refinement_states["quarters"],
        }
        shape = tuple(int(value) for value in seeded.field.shape)
        state_rows: list[dict[str, Any]] = []
        for name, state in raw_states.items():
            raw = _state_raw(state)
            relative = f"fixtures/{name}.f64le"
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            state_rows.append({
                "name": name,
                "path": relative,
                "shape": list(shape),
                "bytes": len(raw),
                "sha256": _hash_bytes(raw),
                "state_sha256": _raw_hash(raw, shape),
            })
        state_rows.sort(key=lambda row: row["name"].encode("utf-8"))
        conjugation_error = float((conjugate_step.candidate.field - _conjugate(seeded_step.candidate).field).abs().amax().item())
        source_rejection = transition_v3_transport(
            seeded,
            geometry_profile=geometry,
            transport_profile=transport,
            duration_s=duration,
            source=b"forbidden",
        )
        controls = {
            "schema": _CONTROLS_SCHEMA,
            "zero_state_exact": bool(torch.equal(zero.field, zero_step.candidate.field)),
            "phase_conjugation_error": conjugation_error,
            "source_rejected": not source_rejection.committable and source_rejection.candidate is None,
            "source_failure_reason": source_rejection.failure_reason,
            "inactive_tail_nonzero": seeded_step.diagnostics.inactive_tail_nonzero,
            "status": "PASS",
        }
        if not controls["zero_state_exact"] or not controls["source_rejected"] or conjugation_error > 1.0e-10:
            raise W3ArtifactError("W3 mutation/equivariance controls failed")
        runtime = {
            "schema": _RUNTIME_SCHEMA,
            "duration_s": duration,
            "state_layout": {"shape": list(shape), "dtype": "float64", "endianness": "little"},
            "states": state_rows,
            "seeded_receipt": _plain(seeded_step.receipt),
            "seeded_diagnostics": _plain(seeded_step.diagnostics),
            "seeded_ledger": _plain(seeded_step.ledger),
            "status": "PASS",
        }
        if seeded_step.diagnostics.damping_work > 0.0 or seeded_step.diagnostics.inactive_tail_nonzero != 0:
            raise W3ArtifactError("W3 damping/tail diagnostics failed")
        _write_json(temporary / "results" / "runtime.json", runtime)
        _write_json(temporary / "results" / "refinement.json", refinement)
        _write_json(temporary / "results" / "long-horizon.json", _long_horizon(transport))
        _write_json(temporary / "results" / "controls.json", controls)

        manifest = {"schema": _MANIFEST_SCHEMA, "objects": _object_rows(temporary)}
        manifest["manifest_sha256"] = _hash_object(_MANIFEST_SCHEMA, manifest)
        _write_json(temporary / "manifest.json", manifest)
        objects = _object_rows(temporary)
        index_core = {
            "schema": _ARTIFACT_SCHEMA,
            "legacy_schema": W3_RUN_INDEX_SCHEMA,
            "status": "PASS_W3_G3",
            "profile_sha256": transport.profile_sha256,
            "contract_root_sha256": transport.contract_root_sha256,
            "semantic_sha256": transport.payload["semantic_sha256"],
            "stage_schedule_sha256": stage_schedule_sha256,
            "parent_w2_run_id": parent_path.name,
            "parent_w2_profile_sha256": geometry.profile_sha256,
            "parent_w2_contract_root_sha256": geometry.contract_root_sha256,
            "source_identity_sha256": source_identity["source_identity_sha256"],
            "manifest_sha256": manifest["manifest_sha256"],
            "objects": objects,
        }
        run_id = _hash_object(W3_ARTIFACT_DOMAIN, index_core)
        index_without_self = {**index_core, "run_id": run_id}
        index = {**index_without_self, "self_sha256": _hash_object(_ARTIFACT_SCHEMA, index_without_self)}
        _write_json(temporary / "index.json", index)

        from verify_cassi_qi_transport import verify_artifact

        verification = verify_artifact(temporary)
        if verification.get("status") != "PASS_W3_G3":
            raise W3ArtifactError("independent W3 verification did not pass")
        destination = root / run_id
        if destination.exists():
            existing = verify_artifact(destination)
            if existing.get("status") != "PASS_W3_G3":
                raise W3ArtifactError("existing W3 artifact is invalid")
            shutil.rmtree(temporary)
        else:
            os.replace(temporary, destination)
            verification = verify_artifact(destination)
        return {"status": "PASS_W3_G3", "artifact": destination.relative_to(_REPOSITORY).as_posix(), "verification": verification}
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        raise
def run_artifact(*, output_root: str | Path | None = None) -> Path:
    """Workflow entry point returning the sealed artifact directory."""
    return _REPOSITORY / run(output_root=output_root)["artifact"]




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run(output_root=args.output_root), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
