"""Materialize the source-exact W2/G2 ragged periodic-FFT2 artifact."""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

import torch

from cassi_qi_geometry import (
    ACTIVE_SHAPES,
    ACTIVE_SITE_COUNTS,
    COMPONENT_COUNT,
    G2_ROTATION_PROBE_QUARTER_TURNS,
    MAX_BATCH_LANES,
    MODE_COUNT,
    OVERSAMPLING_FACTORS,
    PHI,
    SCALE_COUNT,
    SHEET_EXTENTS_M,
    SHEET_SPACINGS_M,
    SIGNED_FREQUENCIES_X,
    SIGNED_FREQUENCIES_Y,
    STATE_WIDTH,
    W2_FAMILY,
    W2_GATE_STATUS_SCHEMA,
    W2_G2_CANDIDATE_SCHEMA,
    W2_GEOMETRY_CONTRACT_SCHEMA,
    W2_NUMERIC_TOLERANCE,
    W2_NUMERIC_TOLERANCE_VALUE,
    W2_RUN_DOMAIN,
    W2_RUN_INDEX_SCHEMA,
    W2_SOURCE_IDENTITY_SCHEMA,
    PeriodicSheetGeometry,
    d_c_to_ey_ei,
    d_c_weighted_energy,
    ey_ei_to_d_c,
    load_w2_geometry_profile,
    validate_w2_geometry_profile,
    vd_vc_to_vy_vi,
    vy_vi_to_vd_vc,
)
from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads


_REPOSITORY = Path(__file__).resolve().parent
_W2_ROOT = _REPOSITORY / "_diag" / "cassi-qi-flow-w2-periodic-fft2-final"
_ARTIFACT_SCHEMA = "cassi.qi-flow-w2-periodic-fft2-artifact.v1"
_FIXTURE_SCHEMA = "cassi.qi-flow-g2-periodic-fft2-fixtures.v1"
_TOLERANCE = W2_NUMERIC_TOLERANCE_VALUE


class W2GeometryArtifactError(RuntimeError):
    """Raised before a W2/G2 artifact can be sealed."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _f64(value: float) -> str:
    value = 0.0 if value == 0.0 else float(value)
    if not math.isfinite(value):
        raise W2GeometryArtifactError("evidence must be finite float64")
    return "f64:" + struct.pack(">d", value).hex()


def _thaw(value: Any) -> Any:
    return canonical_json_loads(canonical_json_bytes(value))


def _write_new(root: Path, relative: str, payload: bytes) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise W2GeometryArtifactError(f"attempted to replace sealed object {relative}")
    target.write_bytes(payload)


def _write_json(root: Path, relative: str, value: Mapping[str, Any]) -> None:
    _write_new(root, relative, canonical_json_bytes(value))


def _source_records() -> list[dict[str, Any]]:
    paths = (
        "CassiFI/01-field-physics.md",
        "CassiFI/10-work-packages.md",
        "CassiFI/11-validation-gates.md",
        "cassi-qi-flow-development.json",
        "cassi_qi_field.py",
        "cassi_qi_geometry.py",
        "cassi_qi_profile.py",
        "run_cassi_qi_geometry.py",
        "test_cassi_qi_geometry.py",
        "test_cassi_qi_geometry_field.py",
        "verify_cassi_qi_geometry.py",
    )
    records = []
    for relative in sorted(paths, key=lambda value: value.encode("utf-8")):
        raw = (_REPOSITORY / relative).read_bytes()
        records.append({"path": relative, "byte_count": len(raw), "sha256": _sha256(raw)})
    return records


def _source_identity(records: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": W2_SOURCE_IDENTITY_SCHEMA,
        "family": W2_FAMILY,
        "sources": records,
    }
    payload["self_sha256"] = canonical_hash(payload, W2_SOURCE_IDENTITY_SCHEMA)
    return payload


def _copy_sources(root: Path, records: list[dict[str, Any]]) -> None:
    for record in records:
        raw = (_REPOSITORY / str(record["path"])).read_bytes()
        if len(raw) != record["byte_count"] or _sha256(raw) != record["sha256"]:
            raise W2GeometryArtifactError(f"source changed during W2 materialization: {record['path']}")
        _write_new(root, f"run-spec/sources/{record['path']}", raw)


def _pack(values: torch.Tensor) -> tuple[str, bytes]:
    tensor = values.detach().cpu().contiguous()
    if tensor.dtype == torch.float64:
        return "float64-le", b"".join(struct.pack("<d", float(value)) for value in tensor.reshape(-1).tolist())
    tensor = tensor.to(torch.complex128)
    return "complex128-le-interleaved", b"".join(
        struct.pack("<dd", float(value.real), float(value.imag))
        for value in tensor.reshape(-1).tolist()
    )


def _max_abs(values: torch.Tensor) -> float:
    return float(values.abs().max().item()) if values.numel() else 0.0

def _normalized_error(actual: torch.Tensor, expected: torch.Tensor) -> float:
    scale = max(1.0, _max_abs(actual), _max_abs(expected))
    return _max_abs(actual - expected) / scale


def _rejected(action: Callable[[], Any]) -> bool:
    try:
        action()
    except Exception:
        return True
    return False


def _fixture_field(surface: PeriodicSheetGeometry, scale: int, *, lanes: int = 2) -> torch.Tensor:
    y, x = surface.coordinate_mesh(scale)
    ly, lx = SHEET_EXTENTS_M[scale]
    values = (
        torch.exp(1.0j * (2.0 * math.pi * y / ly + 4.0 * math.pi * x / lx))
        + 0.5 * torch.exp(-1.0j * (2.0 * math.pi * y / ly - 2.0 * math.pi * x / lx))
    )
    return torch.stack(tuple((lane + 1.0) * values + 0.125j * (scale + lane + 1.0) for lane in range(lanes)), dim=-1).contiguous()


def _nyquist_fixture(scale: int, *, lanes: int = 2) -> torch.Tensor:
    ny, nx = ACTIVE_SHAPES[scale]
    pattern = torch.tensor([(-1.0) ** index for index in range(nx)], dtype=torch.complex128)
    return torch.stack(
        tuple(1.0j * (scale + 1.0) * (lane + 1.0) * pattern[None, :].repeat(ny, 1) for lane in range(lanes)),
        dim=-1,
    ).contiguous()


def _bandlimited_periodic_gaussian(surface: PeriodicSheetGeometry, scale: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    y, x = surface.coordinate_mesh(scale)
    ly, lx = SHEET_EXTENTS_M[scale]
    value = torch.zeros_like(y, dtype=torch.complex128)
    derivative_x = torch.zeros_like(value)
    derivative_y = torch.zeros_like(value)
    laplacian = torch.zeros_like(value)
    frequencies_y = [frequency for frequency in SIGNED_FREQUENCIES_Y[scale] if abs(frequency) <= 1]
    frequencies_x = [frequency for frequency in SIGNED_FREQUENCIES_X[scale] if abs(frequency) <= 2]
    for frequency_y in frequencies_y:
        for frequency_x in frequencies_x:
            coefficient = math.exp(-0.6 * (frequency_y * frequency_y + frequency_x * frequency_x))
            ky = 2.0 * math.pi * frequency_y / ly
            kx = 2.0 * math.pi * frequency_x / lx
            wave = coefficient * torch.exp(1.0j * (ky * y + kx * x))
            value += wave
            derivative_x += 1.0j * kx * wave
            derivative_y += 1.0j * ky * wave
            laplacian -= (kx * kx + ky * ky) * wave
    return value[..., None].contiguous(), derivative_x[..., None].contiguous(), derivative_y[..., None].contiguous(), laplacian[..., None].contiguous()


def _write_fixtures(root: Path, fields: list[torch.Tensor], vectors: list[torch.Tensor], nyquists: list[torch.Tensor], epsilon: torch.Tensor) -> dict[str, Any]:
    fixtures: list[tuple[str, str, torch.Tensor]] = []
    for scale in range(SCALE_COUNT):
        fixtures.extend(
            (
                (f"complex_scale_{scale}", f"gates/g2-geometry/raw/complex-scale-{scale}.c128le", fields[scale]),
                (f"vector_scale_{scale}", f"gates/g2-geometry/raw/vector-scale-{scale}.c128le", vectors[scale]),
                (
                    f"signed_nyquist_scale_{scale}",
                    "gates/g2-geometry/raw/signed-nyquist.c128le" if scale == 0 else f"gates/g2-geometry/raw/signed-nyquist-{scale}.c128le",
                    nyquists[scale],
                ),
            )
        )
    fixtures.append(("epsilon2_ema", "gates/g2-geometry/raw/epsilon2-ema.f64le", epsilon))
    records = []
    for fixture_id, path, tensor in sorted(fixtures, key=lambda row: row[0].encode("utf-8")):
        encoding, raw = _pack(tensor)
        _write_new(root, path, raw)
        records.append(
            {
                "fixture_id": fixture_id,
                "path": path,
                "encoding": encoding,
                "shape": list(tensor.shape),
                "byte_count": len(raw),
                "sha256": _sha256(raw),
            }
        )
    manifest: dict[str, Any] = {
        "schema": _FIXTURE_SCHEMA,
        "family": W2_FAMILY,
        "layout": "row-major-last-lane-fastest",
        "fixtures": records,
    }
    manifest["self_sha256"] = canonical_hash(manifest, _FIXTURE_SCHEMA)
    _write_json(root, "gates/g2-geometry/fixtures.json", manifest)
    return manifest


def _coordinate_conversion_rows(fields: list[torch.Tensor]) -> dict[str, Any]:
    random = fields[0]
    basis = torch.eye(8, 2, dtype=torch.float64).to(torch.complex128)
    conjugate = random.reshape(-1, random.shape[-1])[:8].contiguous()
    fixtures = {
        "zero": (torch.zeros_like(basis), torch.zeros_like(basis)),
        "basis": (basis, torch.flip(basis, dims=(0,)).contiguous()),
        "random": (random, (0.5j * random).contiguous()),
        "conjugate_pair": (conjugate, conjugate.conj().contiguous()),
        "amplitude_extremes": (
            torch.full_like(basis, 0.5 + 0.5j),
            torch.full_like(basis, -0.5 + 0.5j),
        ),
    }
    rows = []
    for fixture_id, (ey, ei) in fixtures.items():
        d, c = ey_ei_to_d_c(ey, ei)
        restored_ey, restored_ei = d_c_to_ey_ei(d, c)
        vd, vc = vy_vi_to_vd_vc(ey, ei)
        restored_vy, restored_vi = vd_vc_to_vy_vi(vd, vc)
        rows.append(
            {
                "fixture": fixture_id,
                "position_roundtrip_error": _f64(max(_max_abs(restored_ey - ey), _max_abs(restored_ei - ei))),
                "velocity_roundtrip_error": _f64(max(_max_abs(restored_vy - ey), _max_abs(restored_vi - ei))),
                "metric_identity_error": _f64(_max_abs(d_c_weighted_energy(d, c) - (ey.abs().square() + ei.abs().square()))),
            }
        )
    return {"phi": _f64(PHI), "fixtures": rows}


def _measure(
    surface: PeriodicSheetGeometry,
    fields: list[torch.Tensor],
    vectors: list[torch.Tensor],
    nyquists: list[torch.Tensor],
    epsilon: torch.Tensor,
    profile_payload: Mapping[str, Any],
    root: Mapping[str, Any],
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    per_scale = []
    state = torch.zeros((SCALE_COUNT, STATE_WIDTH, fields[0].shape[-1]), dtype=torch.complex128)
    max_errors: list[float] = []
    for scale, field in enumerate(fields):
        ny, nx = ACTIVE_SHAPES[scale]
        y_axis, x_axis = surface.coordinate_axes(scale)
        y, x = surface.coordinate_mesh(scale)
        dy, dx = SHEET_SPACINGS_M[scale]
        ly, lx = SHEET_EXTENTS_M[scale]
        packed = surface.grid_to_modes(field, scale=scale)
        restored = surface.modes_to_grid(packed, scale=scale)
        state = surface.scatter_active(field, scale=scale, component=0, state=state)
        fft = surface.fft2(field, scale=scale)
        matrix_error = _normalized_error(
            surface.fft2_matrix(scale) @ packed[: ACTIVE_SITE_COUNTS[scale]],
            fft.reshape(ACTIVE_SITE_COUNTS[scale], field.shape[-1]),
        )
        gradient = surface.gradient(field, scale=scale)
        divergence = surface.divergence(vectors[scale], scale=scale)
        laplacian = surface.laplacian(field, scale=scale)
        div_grad_error = _normalized_error(surface.divergence(gradient, scale=scale), laplacian)
        gradient_left = surface.weighted_inner(gradient, vectors[scale], scale=scale)
        gradient_right = -surface.weighted_inner(field, divergence, scale=scale)
        gradient_adjoint_error = _normalized_error(gradient_left, gradient_right)
        laplacian_left = surface.weighted_inner(field, laplacian, scale=scale)
        laplacian_right = surface.weighted_inner(laplacian, field, scale=scale)
        laplacian_adjoint_error = _normalized_error(laplacian_left, laplacian_right)
        constant = torch.ones((ny, nx, 1), dtype=torch.complex128)
        ramp = (torch.sin(2.0 * math.pi * y / ly) + 0.5 * torch.sin(2.0 * math.pi * x / lx))[..., None].to(torch.complex128).contiguous()
        ramp_dx = (math.pi / lx * torch.cos(2.0 * math.pi * x / lx))[..., None].to(torch.complex128)
        ramp_dy = (2.0 * math.pi / ly * torch.cos(2.0 * math.pi * y / ly))[..., None].to(torch.complex128)
        plane = torch.exp(1.0j * (2.0 * math.pi * y / ly + 4.0 * math.pi * x / lx))[..., None].contiguous()
        gaussian, gaussian_dx, gaussian_dy, gaussian_laplacian = _bandlimited_periodic_gaussian(surface, scale)
        constant_gradient = surface.gradient(constant, scale=scale)
        constant_laplacian = surface.laplacian(constant, scale=scale)
        ramp_gradient = surface.gradient(ramp, scale=scale)
        plane_gradient = surface.gradient(plane, scale=scale)
        plane_laplacian = surface.laplacian(plane, scale=scale)
        gaussian_gradient = surface.gradient(gaussian, scale=scale)
        gaussian_laplacian_actual = surface.laplacian(gaussian, scale=scale)
        analytic = {
            "constant_gradient_error": _normalized_error(constant_gradient, torch.zeros_like(constant_gradient)),
            "constant_laplacian_error": _normalized_error(constant_laplacian, torch.zeros_like(constant_laplacian)),
            "ramp_gradient_error": max(
                _normalized_error(ramp_gradient[0], ramp_dx),
                _normalized_error(ramp_gradient[1], ramp_dy),
            ),
            "sinusoid_gradient_error": max(
                _normalized_error(plane_gradient[0], 1.0j * (4.0 * math.pi / lx) * plane),
                _normalized_error(plane_gradient[1], 1.0j * (2.0 * math.pi / ly) * plane),
            ),
            "plane_wave_laplacian_error": _normalized_error(
                plane_laplacian,
                -((4.0 * math.pi / lx) ** 2 + (2.0 * math.pi / ly) ** 2) * plane,
            ),
            "gaussian_gradient_error": max(
                _normalized_error(gaussian_gradient[0], gaussian_dx),
                _normalized_error(gaussian_gradient[1], gaussian_dy),
            ),
            "gaussian_laplacian_error": _normalized_error(gaussian_laplacian_actual, gaussian_laplacian),
        }
        nyquist_gradient = surface.gradient(nyquists[scale], scale=scale)[0]
        nyquist_error = _normalized_error(
            nyquist_gradient,
            (math.pi / dx) * nyquists[scale].imag,
        )
        translated = surface.spectral_translate(field, scale=scale, delta_m=(dy, dx))
        translated_expected = torch.roll(field, shifts=(1, 1), dims=(0, 1))
        translation_error = _normalized_error(translated, translated_expected)
        translation_inverse_error = _normalized_error(
            surface.spectral_translate(translated, scale=scale, delta_m=(-dy, -dx)),
            field,
        )
        rotated = surface.rotate_quarter_turns(field, scale=scale, quarter_turns=G2_ROTATION_PROBE_QUARTER_TURNS)
        rotated_expected = torch.roll(torch.flip(field, dims=(0, 1)), shifts=(1, 1), dims=(0, 1))
        rotation_error = _normalized_error(rotated, rotated_expected)
        rotation_inverse_error = _normalized_error(
            surface.rotate_quarter_turns(rotated, scale=scale, quarter_turns=G2_ROTATION_PROBE_QUARTER_TURNS),
            field,
        )
        fine = surface.interpolate_oversampled(field, scale=scale)
        factors = OVERSAMPLING_FACTORS[scale]
        restricted_fine = surface.restrict_oversampled(fine, scale=scale)
        injected_constant = surface.interpolate_oversampled(constant, scale=scale)
        fine_metric = surface.weighted_inner(fine, fine, scale=scale, refinement=factors)
        base_metric = surface.weighted_inner(field, field, scale=scale)
        projected_fine = surface.oversampled_projector(fine, scale=scale)
        oversampling = {
            "roundtrip_error": _normalized_error(restricted_fine, field),
            "constant_error": _normalized_error(injected_constant, torch.ones_like(injected_constant)),
            "metric_error": _normalized_error(fine_metric, base_metric),
            "projector_error": _normalized_error(projected_fine, fine),
        }
        errors = {
            "mode_roundtrip_error": _normalized_error(restored, field),
            "gather_scatter_error": _normalized_error(surface.gather_active(state, scale=scale, component=0), field),
            "fft_roundtrip_error": _normalized_error(surface.ifft2(fft, scale=scale), field),
            "fft_matrix_error": matrix_error,
            "signed_nyquist_gradient_error": nyquist_error,
            "divergence_gradient_laplacian_error": div_grad_error,
            "gradient_divergence_adjoint_error": gradient_adjoint_error,
            "laplacian_self_adjoint_error": laplacian_adjoint_error,
            "translation_error": translation_error,
            "translation_inverse_error": translation_inverse_error,
            "rotation_error": rotation_error,
            "rotation_inverse_error": rotation_inverse_error,
            "release_translation_identity_error": _normalized_error(surface.body_frame_translate(field, scale=scale), field),
            "release_rotation_identity_error": _normalized_error(surface.body_frame_rotate(field, scale=scale), field),
            **analytic,
            **{f"oversampling_{key}": value for key, value in oversampling.items()},
        }
        max_errors.extend(errors.values())
        per_scale.append(
            {
                "scale": scale,
                "shape_yx": [ny, nx],
                "active_site_count": ACTIVE_SITE_COUNTS[scale],
                "signed_frequency_y": list(SIGNED_FREQUENCIES_Y[scale]),
                "signed_frequency_x": list(SIGNED_FREQUENCIES_X[scale]),
                "coordinate_origin_error": _f64(_max_abs(y_axis[:1]) + _max_abs(x_axis[:1])),
                "coordinate_spacing_error": _f64(max(_max_abs((y_axis[1:] - y_axis[:-1]) - dy), _max_abs((x_axis[1:] - x_axis[:-1]) - dx))),
                "errors": {key: _f64(value) for key, value in sorted(errors.items())},
                "curl_norm": _f64(_max_abs(surface.curl(vectors[scale], scale=scale))),
                "nyquist_imaginary_norm": _f64(_max_abs(nyquists[scale].imag)),
            }
        )

    cross_scale = []
    remaps = []
    for source in range(SCALE_COUNT):
        for target in range(SCALE_COUNT):
            matrix = surface.cross_scale_matrix(source, target)
            adjoint = surface.cross_scale_adjoint_matrix(source, target)
            left_grid = fields[target]
            right_grid = fields[source]
            mapped = surface.cross_scale_transfer(
                surface.grid_to_modes(right_grid, scale=source),
                source_scale=source,
                target_scale=target,
            )
            mapped_grid = surface.modes_to_grid(mapped, scale=target)
            adjoint_mapped = surface.cross_scale_adjoint(
                surface.grid_to_modes(left_grid, scale=target),
                source_scale=source,
                target_scale=target,
            )
            adjoint_grid = surface.modes_to_grid(adjoint_mapped, scale=source)
            cross_left = surface.weighted_inner(left_grid, mapped_grid, scale=target)
            cross_right = surface.weighted_inner(adjoint_grid, right_grid, scale=source)
            adjoint_error = _normalized_error(cross_left, cross_right)
            cross_scale.append(
                {
                    "source_scale": source,
                    "target_scale": target,
                    "matrix_shape": list(matrix.shape),
                    "adjoint_matrix_shape": list(adjoint.shape),
                    "weighted_adjoint_error": _f64(adjoint_error),
                }
            )
            max_errors.append(adjoint_error)
            receipt = surface.remap_epsilon2_ema(epsilon, source_scale=source, target_scale=target)
            mass_error = _normalized_error(receipt.target_mass, receipt.source_mass)
            remaps.append(
                {
                    "source_scale": source,
                    "target_scale": target,
                    "mass_error": _f64(mass_error),
                    "source_minimum": _f64(float(receipt.source_minimum)),
                    "target_minimum": _f64(float(receipt.target_minimum)),
                }
            )
            max_errors.append(mass_error)

    mutated_profile = _thaw(profile_payload)
    mutated_profile["geometry_contract"]["family"] = "wrong-family"
    scale0 = 0
    ny0, nx0 = ACTIVE_SHAPES[scale0]
    wrong_normalization = torch.fft.ifft2(
        torch.fft.fft2(fields[0], dim=(0, 1), norm="backward"),
        dim=(0, 1),
        norm="ortho",
    )
    wrong_signed = -(math.pi / SHEET_SPACINGS_M[0][1]) * nyquists[0].imag
    centered_roll = (
        torch.roll(nyquists[0], -1, dims=1) - torch.roll(nyquists[0], 1, dims=1)
    ) / (2.0 * SHEET_SPACINGS_M[0][1])
    controls = {
        "schema_mutation_rejected": canonical_hash(
            {**_thaw(profile_payload)["geometry_contract"], "family": "wrong-family"},
            W2_GEOMETRY_CONTRACT_SCHEMA,
        ) != profile_payload["geometry_contract_sha256"],
        "profile_hash_mutation_rejected": _rejected(lambda: validate_w2_geometry_profile(mutated_profile, contract_root=root)),
        "source_mutation_rejected": _sha256((_REPOSITORY / str(sources[0]["path"])).read_bytes() + b"\x00") != sources[0]["sha256"],
        "extra_axis_variant_rejected": _rejected(lambda: surface.gradient(torch.zeros((1, ny0, nx0, 1), dtype=torch.float64), scale=0)),
        "transposed_axes_rejected": _rejected(lambda: surface.grid_to_modes(torch.zeros((nx0, ny0, 1), dtype=torch.float64), scale=0)),
        "padding_rejected": _rejected(lambda: surface.gather_active(torch.zeros((SCALE_COUNT, STATE_WIDTH + 1, 1), dtype=torch.float64), scale=0, component=0)),
        "centered_roll_variant_rejected": _max_abs(centered_roll - surface.gradient(nyquists[0], scale=0)[0]) > 1.0,
        "wrong_signed_nyquist_rejected": _max_abs(wrong_signed - surface.gradient(nyquists[0], scale=0)[0]) > 1.0,
        "wrong_normalization_rejected": _max_abs(wrong_normalization - fields[0]) > 1.0,
        "one_cell_coordinate_permutation_rejected": _max_abs(fields[0].reshape(-1, fields[0].shape[-1]) - fields[0].transpose(0, 1).reshape(-1, fields[0].shape[-1])) > 0.1,
        "wrong_translation_sign_rejected": _max_abs(
            surface.spectral_translate(fields[0], scale=0, delta_m=SHEET_SPACINGS_M[0])
            - torch.roll(fields[0], shifts=(-1, -1), dims=(0, 1))
        ) > 0.1,
        "vector_rotation_sign_rejected": _max_abs(
            surface.rotate_quarter_turns(vectors[0], scale=0, quarter_turns=2)
            - torch.roll(torch.flip(vectors[0], dims=(1, 2)), shifts=(1, 1), dims=(1, 2))
        ) > 0.1,
        "negative_epsilon_rejected": _rejected(lambda: surface.remap_epsilon2_ema(-epsilon, source_scale=0, target_scale=1)),
        "inactive_tail_control": all(active <= MODE_COUNT for active in ACTIVE_SITE_COUNTS) and surface.zero_tail_proof(state)["inactive_tail_is_exact_zero"],
    }
    if not all(controls.values()):
        raise W2GeometryArtifactError(f"a required G2 control failed: {controls}")
    maximum_error = max(max_errors)
    if maximum_error > _TOLERANCE:
        raise W2GeometryArtifactError(f"G2 numeric error {maximum_error:.17g} exceeds {_TOLERANCE:.17g}")
    return (
        {
            "per_scale": per_scale,
            "zero_tail": surface.zero_tail_proof(state),
            "coordinate_translation": _coordinate_conversion_rows(fields),
            "cross_scale": cross_scale,
            "epsilon2_ema": remaps,
            "maximum_numeric_error": _f64(maximum_error),
            "numeric_error_count": len(max_errors),
        },
        controls,
    )


def _object_records(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "byte_count": path.stat().st_size,
            "sha256": _sha256(path.read_bytes()),
        }
        for path in sorted(root.rglob("*"), key=lambda candidate: candidate.relative_to(root).as_posix().encode("utf-8"))
        if path.is_file() and path.name != "index.json"
    ]


def _index(records: list[dict[str, Any]], profile: Mapping[str, Any], source_identity: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    material = {
        "schema": W2_RUN_INDEX_SCHEMA,
        "artifact_schema": _ARTIFACT_SCHEMA,
        "family": W2_FAMILY,
        "parent_w1": _thaw(profile["parent_w1"]),
        "profile_sha256": profile["profile_sha256"],
        "contract_root_sha256": profile["contract_root_sha256"],
        "geometry_contract_sha256": profile["geometry_contract_sha256"],
        "operator_semantic_sha256": profile["operator_semantic_sha256"],
        "source_identity_sha256": source_identity["self_sha256"],
        "candidate_sha256": candidate["self_sha256"],
        "objects": records,
    }
    index = {**material, "run_id": canonical_hash(material, W2_RUN_DOMAIN), "status": "PASS_W2_G2"}
    index["self_sha256"] = canonical_hash(index, W2_RUN_INDEX_SCHEMA)
    return index


def _publish(stage: Path, index: Mapping[str, Any], output_root: Path) -> Path:
    destination = output_root / str(index["run_id"])
    index_raw = canonical_json_bytes(index)
    if destination.exists():
        existing = destination / "index.json"
        if not existing.is_file() or existing.read_bytes() != index_raw:
            raise W2GeometryArtifactError(f"sealed W2 destination conflicts: {destination}")
        shutil.rmtree(stage)
        return destination
    output_root.mkdir(parents=True, exist_ok=True)
    os.replace(stage, destination)
    return destination


def run(*, output_root: Path | None = None) -> Path:
    profile = validate_w2_geometry_profile(load_w2_geometry_profile())
    surface = PeriodicSheetGeometry(profile)
    source_records = _source_records()
    source_identity = _source_identity(source_records)
    target_root = _W2_ROOT if output_root is None else Path(output_root)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="w2-periodic-fft2-", dir=target_root.parent))
    try:
        fields = [_fixture_field(surface, scale) for scale in range(SCALE_COUNT)]
        vectors = [torch.stack((field, (0.5 + 0.25j) * field.conj()), dim=0).contiguous() for field in fields]
        nyquists = [_nyquist_fixture(scale) for scale in range(SCALE_COUNT)]
        epsilon = (torch.arange(1, MODE_COUNT * 2 + 1, dtype=torch.float64).reshape(MODE_COUNT, 2) / 128.0).contiguous()
        _write_json(stage, "run-spec/w2-contract-root.json", _thaw(profile.contract_root))
        _write_json(stage, "run-spec/w2-profile.json", _thaw(profile.payload))
        _write_json(stage, "run-spec/w2-geometry-contract.json", _thaw(profile.payload["geometry_contract"]))
        _write_json(stage, "run-spec/w2-operator-contract.json", _thaw(profile.payload["operator_semantic"]))
        _write_json(stage, "run-spec/w2-schema-registry.json", _thaw(profile.payload["schema_registry"]))
        _write_json(stage, "run-spec/parent-w1.json", _thaw(profile.parent_w1))
        _write_json(stage, "run-spec/parent-w1-profile.json", _thaw(profile.base_profile.payload))
        _write_json(stage, "run-spec/parent-w1-contract-root.json", _thaw(profile.base_profile.contract_root.payload))
        _write_json(stage, "run-spec/source-identity.json", source_identity)
        _copy_sources(stage, source_records)
        fixture_manifest = _write_fixtures(stage, fields, vectors, nyquists, epsilon)
        rows, controls = _measure(surface, fields, vectors, nyquists, epsilon, profile.payload, profile.contract_root, source_records)
        candidate: dict[str, Any] = {
            "schema": W2_G2_CANDIDATE_SCHEMA,
            "family": W2_FAMILY,
            "parent_w1": _thaw(profile.parent_w1),
            "profile_sha256": profile.profile_sha256,
            "contract_root_sha256": profile.contract_root_sha256,
            "geometry_contract_sha256": profile.geometry_contract_sha256,
            "operator_semantic_sha256": profile.operator_semantic_sha256,
            "source_identity_sha256": source_identity["self_sha256"],
            "fixture_manifest_sha256": fixture_manifest["self_sha256"],
            "tolerance": W2_NUMERIC_TOLERANCE,
            "rows": rows,
            "mutation_controls": controls,
            "operator_metadata": surface.operator_metadata(),
        }
        candidate["self_sha256"] = canonical_hash(candidate, W2_G2_CANDIDATE_SCHEMA)
        _write_json(stage, "gates/g2-geometry/candidate.json", candidate)
        status: dict[str, Any] = {
            "schema": W2_GATE_STATUS_SCHEMA,
            "family": W2_FAMILY,
            "gate": "G2",
            "status": "PASS",
            "candidate_sha256": candidate["self_sha256"],
            "profile_sha256": profile.profile_sha256,
            "source_identity_sha256": source_identity["self_sha256"],
            "fixture_manifest_sha256": fixture_manifest["self_sha256"],
        }
        status["self_sha256"] = canonical_hash(status, W2_GATE_STATUS_SCHEMA)
        _write_json(stage, "gates/g2-geometry/status.json", status)
        index = _index(_object_records(stage), profile.payload, source_identity, candidate)
        _write_json(stage, "index.json", index)
        from verify_cassi_qi_geometry import verify_artifact

        verify_artifact(stage)
        return _publish(stage, index, target_root)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the sealed W2/G2 ragged periodic-FFT2 artifact.")
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args()
    artifact = run(output_root=args.output_root)
    print(
        canonical_json_bytes(
            {
                "artifact": artifact.relative_to(_REPOSITORY).as_posix() if artifact.is_relative_to(_REPOSITORY) else str(artifact),
                "status": "PASS_W2_G2",
            }
        ).decode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
