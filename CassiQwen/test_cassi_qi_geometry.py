from __future__ import annotations

import math
import shutil
import tempfile
import unittest
from pathlib import Path

import torch

import cassi_qi_geometry
from cassi_qi_geometry import (
    ACTIVE_SHAPES,
    ACTIVE_SITE_COUNTS,
    COMPONENT_COUNT,
    MAX_BATCH_LANES,
    MODE_COUNT,
    OVERSAMPLING_FACTORS,
    PHI,
    SCALE_COUNT,
    SHEET_CELL_AREAS_M2,
    SHEET_EXTENTS_M,
    SHEET_SPACINGS_M,
    SIGNED_FREQUENCIES_X,
    SIGNED_FREQUENCIES_Y,
    STATE_WIDTH,
    VECTOR_ORDER,
    W2_FAMILY,
    W2_NUMERIC_TOLERANCE_VALUE,
    W_C,
    W_D,
    Epsilon2RemapReceipt,
    PeriodicSheetGeometry,
    VerificationError,
    d_c_to_ey_ei,
    d_c_weighted_energy,
    ey_ei_to_d_c,
    flat_mode_index,
    load_w2_geometry_profile,
    unflatten_mode_index,
    validate_w2_geometry_profile,
    vd_vc_to_vy_vi,
    vy_vi_to_vd_vc,
)
from cassi_qi_profile import PROFILE_MISMATCH, canonical_json_bytes, canonical_json_loads
from run_cassi_qi_geometry import run
from verify_cassi_qi_geometry import W2GeometryVerificationError, verify_artifact


class PeriodicSheetGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_w2_geometry_profile()
        cls.surface = PeriodicSheetGeometry(cls.profile)
        cls.atol = max(W2_NUMERIC_TOLERANCE_VALUE, 1.0e-9)

    @staticmethod
    def _complex(shape: tuple[int, ...], *, seed: int) -> torch.Tensor:
        generator = torch.Generator(device="cpu").manual_seed(seed)
        return (
            torch.randn(shape, dtype=torch.float64, generator=generator)
            + 1.0j * torch.randn(shape, dtype=torch.float64, generator=generator)
        ).contiguous()

    def test_profile_binds_exact_per_scale_w1_geometry(self) -> None:
        geometry = self.profile.payload["geometry_contract"]
        self.assertEqual(geometry["family"], W2_FAMILY)
        self.assertEqual(
            geometry["storage"],
            {
                "shape": "[S,9M,B]",
                "scale_count": SCALE_COUNT,
                "component_count": COMPONENT_COUNT,
                "mode_count": MODE_COUNT,
                "component_stride": MODE_COUNT,
                "state_width": STATE_WIDTH,
                "batch_limit": MAX_BATCH_LANES,
                "active_site_order": "x-fastest/y-major",
                "inactive_tail": "exact-zero",
            },
        )
        self.assertEqual(list(geometry["axes"]["sheet_axis_order"]), ["y", "x"])
        self.assertEqual(list(geometry["axes"]["vector_component_order"]), list(VECTOR_ORDER))
        self.assertEqual(
            [tuple(sheet["active_rectangle"]["shape_yx"]) for sheet in geometry["per_scale_sheets"]],
            list(ACTIVE_SHAPES),
        )
        self.assertEqual(
            [sheet["active_site_count"] for sheet in geometry["per_scale_sheets"]],
            list(ACTIVE_SITE_COUNTS),
        )
        self.assertEqual(geometry["fft2"]["normalization"], "ortho")
        self.assertEqual(geometry["metric"]["base"], "W_s=dx_s*dy_s*I")
        self.assertFalse(hasattr(self.surface, "laplacian_s"))
        self.assertFalse(hasattr(self.surface, "laplacian_perp"))
        self.assertFalse(hasattr(cassi_qi_geometry, "CENTERED_ROLL"))
        altered = canonical_json_loads(canonical_json_bytes(self.profile.payload))
        altered["geometry_contract"]["per_scale_sheets"][0]["origin_m"][0] = "f64:3f50624dd2f1a9fc"
        with self.assertRaises(PROFILE_MISMATCH):
            validate_w2_geometry_profile(altered, base_profile=self.profile.base_profile)

    def test_x_fastest_active_maps_and_zero_tails_per_scale(self) -> None:
        state = torch.zeros((SCALE_COUNT, STATE_WIDTH, 2), dtype=torch.float64)
        for scale, ((ny, nx), active_count) in enumerate(zip(ACTIVE_SHAPES, ACTIVE_SITE_COUNTS)):
            modes = torch.zeros((MODE_COUNT, 2), dtype=torch.float64)
            modes[:active_count] = torch.arange(active_count * 2, dtype=torch.float64).reshape(active_count, 2)
            grid = self.surface.modes_to_grid(modes, scale=scale)
            self.assertEqual(tuple(grid.shape), (ny, nx, 2))
            self.assertEqual(grid.data_ptr(), modes.data_ptr())
            restored = self.surface.grid_to_modes(grid, scale=scale)
            torch.testing.assert_close(restored, modes, rtol=0.0, atol=0.0)
            for y in range(ny):
                for x in range(nx):
                    mode = flat_mode_index(y, x, scale=scale)
                    self.assertEqual(mode, y * nx + x)
                    self.assertEqual(unflatten_mode_index(mode, scale=scale), (y, x))
            y_axis, x_axis = self.surface.coordinate_axes(scale)
            y_grid, x_grid = self.surface.coordinate_mesh(scale)
            dy, dx = SHEET_SPACINGS_M[scale]
            torch.testing.assert_close(y_axis, torch.arange(ny, dtype=torch.float64) * dy, rtol=0.0, atol=0.0)
            torch.testing.assert_close(x_axis, torch.arange(nx, dtype=torch.float64) * dx, rtol=0.0, atol=0.0)
            torch.testing.assert_close(y_grid[:, 0], y_axis, rtol=0.0, atol=0.0)
            torch.testing.assert_close(x_grid[0], x_axis, rtol=0.0, atol=0.0)
            state = self.surface.scatter_active(grid, scale=scale, component=7, state=state)
            torch.testing.assert_close(self.surface.gather_active(state, scale=scale, component=7), grid, rtol=0.0, atol=0.0)
        self.assertTrue(self.surface.zero_tail_proof(state)["inactive_tail_is_exact_zero"])

    def test_fft2_analytic_fixtures_and_literal_signed_nyquist_every_scale(self) -> None:
        for scale, (ny, nx) in enumerate(ACTIVE_SHAPES):
            y, x = self.surface.coordinate_mesh(scale)
            ly, lx = SHEET_EXTENTS_M[scale]
            ones = torch.ones((ny, nx, 2), dtype=torch.complex128)
            torch.testing.assert_close(self.surface.gradient(ones, scale=scale), torch.zeros((2, ny, nx, 2), dtype=torch.complex128), rtol=0.0, atol=self.atol)
            torch.testing.assert_close(self.surface.laplacian(ones, scale=scale), torch.zeros_like(ones), rtol=0.0, atol=self.atol)

            wave = torch.exp(1.0j * (2.0 * torch.pi * y / ly + 4.0 * torch.pi * x / lx))[..., None].repeat(1, 1, 2).contiguous()
            gradient = self.surface.gradient(wave, scale=scale)
            torch.testing.assert_close(gradient[0], 1.0j * (4.0 * torch.pi / lx) * wave, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(gradient[1], 1.0j * (2.0 * torch.pi / ly) * wave, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(
                self.surface.laplacian(wave, scale=scale),
                -((4.0 * torch.pi / lx) ** 2 + (2.0 * torch.pi / ly) ** 2) * wave,
                rtol=2.0e-15,
                atol=self.atol,
            )

            gaussian = torch.zeros((ny, nx), dtype=torch.complex128)
            expected_dx = torch.zeros_like(gaussian)
            expected_dy = torch.zeros_like(gaussian)
            for frequency_y in (value for value in SIGNED_FREQUENCIES_Y[scale] if abs(value) <= 1):
                for frequency_x in (value for value in SIGNED_FREQUENCIES_X[scale] if abs(value) <= 2):
                    coefficient = math.exp(-0.6 * (frequency_y * frequency_y + frequency_x * frequency_x))
                    ky = 2.0 * math.pi * frequency_y / ly
                    kx = 2.0 * math.pi * frequency_x / lx
                    mode = coefficient * torch.exp(1.0j * (ky * y + kx * x))
                    gaussian += mode
                    expected_dx += 1.0j * kx * mode
                    expected_dy += 1.0j * ky * mode
            gaussian = gaussian[..., None].contiguous()
            gaussian_gradient = self.surface.gradient(gaussian, scale=scale)
            torch.testing.assert_close(gaussian_gradient[0], expected_dx[..., None], rtol=2.0e-15, atol=self.atol)
            torch.testing.assert_close(gaussian_gradient[1], expected_dy[..., None], rtol=2.0e-15, atol=self.atol)

            nyquist_pattern = torch.tensor([(-1.0) ** x_index for x_index in range(nx)], dtype=torch.complex128)
            nyquist = (1.0j * nyquist_pattern[None, :, None]).repeat(ny, 1, 2).contiguous()
            expected = (torch.pi / SHEET_SPACINGS_M[scale][1] * nyquist.imag).to(torch.complex128)
            torch.testing.assert_close(self.surface.gradient(nyquist, scale=scale)[0], expected, rtol=0.0, atol=self.atol)
            transformed = self.surface.fft2(nyquist, scale=scale)
            torch.testing.assert_close(self.surface.ifft2(transformed, scale=scale), nyquist, rtol=0.0, atol=self.atol)
            self.assertEqual(tuple(self.surface.frequency_axes(scale)[0].tolist()), SIGNED_FREQUENCIES_Y[scale])
            self.assertEqual(tuple(self.surface.frequency_axes(scale)[1].tolist()), SIGNED_FREQUENCIES_X[scale])

    def test_spectral_identities_and_spatial_transforms_every_scale(self) -> None:
        for scale, (ny, nx) in enumerate(ACTIVE_SHAPES):
            field = self._complex((ny, nx, 2), seed=31 + scale)
            vector = self._complex((2, ny, nx, 2), seed=41 + scale)
            gradient = self.surface.gradient(field, scale=scale)
            divergence = self.surface.divergence(vector, scale=scale)
            laplacian = self.surface.laplacian(field, scale=scale)
            torch.testing.assert_close(self.surface.divergence(gradient, scale=scale), laplacian, rtol=0.0, atol=1.0e-7)
            left = self.surface.weighted_inner(gradient, vector, scale=scale)
            right = self.surface.weighted_inner(field, divergence, scale=scale)
            torch.testing.assert_close(left + right, torch.zeros_like(left), rtol=0.0, atol=1.0e-8)
            torch.testing.assert_close(
                self.surface.weighted_inner(field, laplacian, scale=scale),
                self.surface.weighted_inner(laplacian, field, scale=scale),
                rtol=0.0,
                atol=1.0e-8,
            )
            dy, dx = SHEET_SPACINGS_M[scale]
            translated = self.surface.spectral_translate(field, scale=scale, delta_m=(dy, dx))
            torch.testing.assert_close(translated, torch.roll(field, shifts=(1, 1), dims=(0, 1)), rtol=0.0, atol=self.atol)
            torch.testing.assert_close(
                self.surface.spectral_translate(translated, scale=scale, delta_m=(-dy, -dx)),
                field,
                rtol=0.0,
                atol=self.atol,
            )
            rotated = self.surface.rotate_quarter_turns(field, scale=scale, quarter_turns=2)
            torch.testing.assert_close(self.surface.rotate_quarter_turns(rotated, scale=scale, quarter_turns=2), field, rtol=0.0, atol=0.0)
            vector_rotated = self.surface.rotate_quarter_turns(vector, scale=scale, quarter_turns=2)
            torch.testing.assert_close(self.surface.rotate_quarter_turns(vector_rotated, scale=scale, quarter_turns=2), vector, rtol=0.0, atol=0.0)
            torch.testing.assert_close(self.surface.body_frame_translate(field, scale=scale), field, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(self.surface.body_frame_rotate(field, scale=scale), field, rtol=0.0, atol=0.0)

    def test_coordinate_conversions_cover_zero_basis_random_conjugate_and_extremes(self) -> None:
        fixtures = [
            (torch.zeros((8, 2), dtype=torch.complex128), torch.zeros((8, 2), dtype=torch.complex128)),
            (torch.eye(8, 2, dtype=torch.float64).to(torch.complex128), torch.flip(torch.eye(8, 2, dtype=torch.float64), dims=(0,)).to(torch.complex128)),
            (self._complex((8, 2), seed=71), self._complex((8, 2), seed=73)),
        ]
        conjugate = self._complex((8, 2), seed=79)
        fixtures.append((conjugate, conjugate.conj().contiguous()))
        fixtures.append((torch.full((8, 2), 0.5 + 0.5j, dtype=torch.complex128), torch.full((8, 2), -0.5 + 0.5j, dtype=torch.complex128)))
        for ey, ei in fixtures:
            d, c = ey_ei_to_d_c(ey, ei)
            restored_ey, restored_ei = d_c_to_ey_ei(d, c)
            torch.testing.assert_close(restored_ey, ey, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(restored_ei, ei, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(d_c_weighted_energy(d, c), ey.abs().square() + ei.abs().square(), rtol=0.0, atol=self.atol)
            vd, vc = vy_vi_to_vd_vc(ey, ei)
            restored_vy, restored_vi = vd_vc_to_vy_vi(vd, vc)
            torch.testing.assert_close(restored_vy, ey, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(restored_vi, ei, rtol=0.0, atol=self.atol)
        self.assertAlmostEqual(W_D * (1.0 + PHI * PHI), 1.0)
        self.assertAlmostEqual(W_C, 1.0 + PHI * PHI)

    def test_cross_scale_remap_and_oversampling(self) -> None:
        for scale, (ny, nx) in enumerate(ACTIVE_SHAPES):
            field = self._complex((ny, nx, 2), seed=91 + scale)
            factors = OVERSAMPLING_FACTORS[scale]
            fine = self.surface.interpolate_oversampled(field, scale=scale)
            torch.testing.assert_close(self.surface.restrict_oversampled(fine, scale=scale), field, rtol=0.0, atol=self.atol)
            torch.testing.assert_close(
                self.surface.weighted_inner(fine, fine, scale=scale, refinement=factors),
                self.surface.weighted_inner(field, field, scale=scale),
                rtol=0.0,
                atol=1.0e-10,
            )
            torch.testing.assert_close(self.surface.oversampled_projector(fine, scale=scale), fine, rtol=0.0, atol=self.atol)
        source = torch.arange(1, MODE_COUNT * 2 + 1, dtype=torch.float64).reshape(MODE_COUNT, 2) / 128.0
        source = source.contiguous()
        for target in range(SCALE_COUNT):
            mapped = self.surface.cross_scale_transfer(source.to(torch.complex128), source_scale=0, target_scale=target)
            torch.testing.assert_close(mapped, source.to(torch.complex128), rtol=0.0, atol=self.atol)
            receipt = self.surface.remap_epsilon2_ema(source, source_scale=0, target_scale=target)
            self.assertIsInstance(receipt, Epsilon2RemapReceipt)
            torch.testing.assert_close(receipt.source_mass, receipt.target_mass, rtol=0.0, atol=self.atol)
            self.assertGreaterEqual(float(receipt.target_minimum), 0.0)
        identity = torch.eye(ACTIVE_SITE_COUNTS[0], dtype=torch.complex128)
        torch.testing.assert_close(self.surface.cross_scale_matrix(0, 3), identity, rtol=0.0, atol=0.0)
        torch.testing.assert_close(self.surface.metric_matrix(0), identity * SHEET_CELL_AREAS_M2[0], rtol=0.0, atol=0.0)

    def test_invalid_layout_axis_and_tail_controls_fail(self) -> None:
        scale = 0
        ny, nx = ACTIVE_SHAPES[scale]
        field = torch.zeros((ny, nx, 1), dtype=torch.float64)
        with self.assertRaises(VerificationError):
            self.surface.grid_to_modes(field.to(torch.float32), scale=scale)
        with self.assertRaises(VerificationError):
            self.surface.grid_to_modes(torch.zeros((nx, ny, 1), dtype=torch.float64), scale=scale)
        with self.assertRaises(VerificationError):
            self.surface.gather_active(torch.zeros((SCALE_COUNT, STATE_WIDTH + 1, 1), dtype=torch.float64), scale=scale, component=0)
        with self.assertRaises(VerificationError):
            flat_mode_index(-1, 0, scale=scale)
        with self.assertRaises(VerificationError):
            unflatten_mode_index(ACTIVE_SITE_COUNTS[scale], scale=scale)
        with self.assertRaises(VerificationError):
            self.surface.rotate_quarter_turns(field, scale=scale, quarter_turns=1)
        with self.assertRaises(VerificationError):
            self.surface.divergence(torch.zeros((2, nx, ny, 1), dtype=torch.float64), scale=scale)
        with self.assertRaises(VerificationError):
            self.surface.weighted_inner(field[..., :0].contiguous(), field[..., :0].contiguous(), scale=scale)
        if ACTIVE_SITE_COUNTS[scale] < MODE_COUNT:
            packed = torch.zeros((MODE_COUNT, 1), dtype=torch.float64)
            packed[ACTIVE_SITE_COUNTS[scale]] = 1.0
            with self.assertRaises(VerificationError):
                self.surface.modes_to_grid(packed, scale=scale)


class W2GeometryArtifactTests(unittest.TestCase):
    def test_content_addressed_driver_and_independent_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "sealed"
            artifact = run(output_root=output_root)
            first = verify_artifact(artifact)
            second = verify_artifact(artifact)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "PASS_W2_G2")
            tampered = Path(directory) / "tampered"
            shutil.copytree(artifact, tampered)
            raw = tampered / "gates" / "g2-geometry" / "raw" / "signed-nyquist.c128le"
            raw.write_bytes(raw.read_bytes()[:-1] + b"\x00")
            with self.assertRaises(W2GeometryVerificationError):
                verify_artifact(tampered)


if __name__ == "__main__":
    unittest.main()
