from __future__ import annotations

import unittest

import torch

from cassi_qi_field import QiFlowStateV3, bind_v3_geometry
from cassi_qi_geometry import ACTIVE_SHAPES, MODE_COUNT, load_w2_geometry_profile
from cassi_qi_profile import PROFILE_MISMATCH


class W2GeometryFieldIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_w2_geometry_profile()

    def _state(self) -> QiFlowStateV3:
        state = QiFlowStateV3.create(self.profile.base_profile, batch_lanes=4, device="cpu")
        values = torch.arange(state.field.numel(), dtype=torch.float64).reshape_as(state.field)
        state.field.copy_((values + 1.0) / float(4 * (values.numel() + 1)))
        return state

    def test_component_view_is_the_single_frozen_mode_tensor(self) -> None:
        state = self._state()
        before = state.field.clone()
        geometry = bind_v3_geometry(state, self.profile)
        scale = 2
        ny, nx = ACTIVE_SHAPES[scale]
        modes = geometry.component_modes(scale, 5)
        grid = geometry.component_grid(scale, 5)
        self.assertEqual(tuple(modes.shape), (MODE_COUNT, 4))
        self.assertEqual(tuple(grid.shape), (ny, nx, 4))
        self.assertEqual(modes.data_ptr(), grid.data_ptr())
        torch.testing.assert_close(geometry.grid_modes(scale, grid), modes, rtol=0.0, atol=0.0)
        identity = geometry.laplacian_identity(scale, 5)
        self.assertLessEqual(float(identity["identity_residual"].abs().max().item()), 1.0e-11)
        self.assertEqual(tuple(geometry.gradient(scale, 5).shape), (2, ny, nx, 4))
        self.assertEqual(tuple(geometry.divergence(scale).shape), (ny, nx, 4))
        self.assertEqual(tuple(geometry.curl(scale).shape), (ny, nx, 4))
        self.assertEqual(tuple(geometry.cross_scale_transfer(5, source_scale=scale, target_scale=0).shape), (*ACTIVE_SHAPES[0], 4))
        receipt = geometry.remap_epsilon2_ema(source_scale=scale, target_scale=0)
        torch.testing.assert_close(receipt.source_mass, receipt.target_mass, rtol=0.0, atol=1.0e-12)
        metadata = geometry.operator_metadata()
        self.assertEqual(metadata["geometry_profile_sha256"], self.profile.profile_sha256)
        self.assertEqual(metadata["geometry_contract_root_sha256"], self.profile.contract_root_sha256)
        self.assertEqual(metadata["operator_semantic_sha256"], self.profile.operator_semantic_sha256)
        torch.testing.assert_close(state.field, before, rtol=0.0, atol=0.0)

    def test_bad_geometry_indices_and_lane_order_fail_before_state_mutation(self) -> None:
        state = self._state()
        before = state.field.clone()
        geometry = bind_v3_geometry(state, self.profile)
        with self.assertRaises(PROFILE_MISMATCH):
            geometry.component_grid(4, 0)
        with self.assertRaises(PROFILE_MISMATCH):
            geometry.component_grid(0, 9)
        with self.assertRaises(PROFILE_MISMATCH):
            geometry.vector_grid(0, (0, 0))
        with self.assertRaises(ValueError):
            geometry.grid_modes(0, geometry.component_grid(0, 0).permute(1, 0, 2))
        torch.testing.assert_close(state.field, before, rtol=0.0, atol=0.0)


if __name__ == "__main__":
    unittest.main()
