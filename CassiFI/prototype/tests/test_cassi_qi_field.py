"""Focused executable contracts for the canonical Qi multi-scale controller."""

from __future__ import annotations

import hashlib
import io
import math
import tempfile
import unittest
from pathlib import Path

import torch

from cassi_qi_field import (
    QI_COMPONENT_ORDER,
    QI_FIELD_LAYOUT_ID,
    QI_FIELD_STATE_SCHEMA,
    QiFieldConfig,
    QiFieldController,
    QiFieldError,
    QiFieldState,
    QiFlowStateV3,
    dump_v3_state_bytes,
    load_v3_checkpoint,
    load_v3_state_bytes,
    save_v3_checkpoint,
)
from cassi_qi_profile import PROFILE_MISMATCH, QiFlowProfile


class QiFieldTests(unittest.TestCase):
    @staticmethod
    def config(*, scales: int = 3, modes: int = 32, alphabet: int = 16) -> QiFieldConfig:
        return QiFieldConfig(scale_count=scales, mode_count=modes, alphabet_size=alphabet)

    @staticmethod
    def parts(controller: QiFieldController, state: QiFieldState) -> list[torch.Tensor]:
        packed = state.field.reshape(
            controller.config.scale_count,
            9,
            controller.config.mode_count,
            state.batch_size,
        )
        return [packed[:, index] for index in range(9)]

    @staticmethod
    def differential_state(
        controller: QiFieldController,
        aligned_by_scale: list[torch.Tensor],
    ) -> QiFieldState:
        """Build a state whose active differential coordinates are supplied aligned."""

        state = controller.initial_state(1, dtype=torch.float64)
        packed = state.field.reshape(
            controller.config.scale_count,
            9,
            controller.config.mode_count,
            1,
        )
        denominator = 1.0 + controller.config.phi**2
        width = controller.config.wave_mode_count
        for scale, aligned in enumerate(aligned_by_scale):
            raw = controller._unalign_active(aligned.reshape(width, 1), scale)[:, 0]
            packed[scale, 0, :width, 0] = raw / denominator
            packed[scale, 2, :width, 0] = -controller.config.phi * raw / denominator
        return QiFieldState(state.field)

    def test_zero_state_abstains_and_metrics_are_finite(self) -> None:
        controller = QiFieldController(self.config(scales=3, modes=32, alphabet=16))
        state = controller.initial_state(2)
        emission = controller.emit(state)
        diagnostics = controller.diagnostics(state)

        self.assertEqual(tuple(state.field.shape), (3, 288, 2))
        self.assertTrue(torch.equal(emission.symbols, torch.full((2,), -1, dtype=torch.int64)))
        self.assertFalse(bool(emission.available.any()))
        self.assertTrue(torch.equal(emission.scores, torch.zeros_like(emission.scores)))
        self.assertFalse(bool(diagnostics.available.any()))
        self.assertTrue(torch.equal(diagnostics.q, torch.zeros_like(diagnostics.q)))
        self.assertTrue(torch.equal(diagnostics.chi, torch.zeros_like(diagnostics.chi)))
        self.assertTrue(torch.isfinite(diagnostics.rho).all())
        self.assertTrue(torch.isfinite(emission.scores).all())

    def test_resonance_scores_are_deterministic_finite_and_batched(self) -> None:
        controller = QiFieldController(self.config(scales=3, modes=32, alphabet=16))
        state = controller.sense_symbols(controller.initial_state(2), [1, 2])
        first = controller.resonance_scores(state)
        second = controller.resonance_scores(state)

        self.assertEqual(tuple(first.shape), (2, 16))
        self.assertTrue(torch.isfinite(first).all())
        torch.testing.assert_close(second, first, rtol=0.0, atol=0.0)
        self.assertFalse(torch.equal(first[0], first[1]))

    def test_emission_supports_fixed_phase_and_symbol_probes(self) -> None:
        controller = QiFieldController(self.config(scales=3, modes=32, alphabet=16))
        state = controller.sense_symbols(controller.initial_state(1), [3])
        baseline = controller.emit(state)
        unchanged = controller.emit(state, phase_radians=0.0)
        torch.testing.assert_close(unchanged.scores, baseline.scores, rtol=0.0, atol=0.0)
        torch.testing.assert_close(unchanged.wave, baseline.wave, rtol=0.0, atol=0.0)

        allowed = (4, 5, 6)
        probe = controller.emit(
            state,
            phase_radians=1.0,
            allowed_symbols=allowed,
        )
        self.assertTrue(bool(probe.available.item()))
        self.assertIn(int(probe.symbols.item()), allowed)
        self.assertTrue(torch.isfinite(probe.scores).all())
        disallowed = [symbol for symbol in range(16) if symbol not in allowed]
        self.assertTrue(
            torch.all(
                probe.scores[0, disallowed]
                == torch.finfo(probe.scores.dtype).min
            )
        )

    def test_canonical_q_epsilon_and_equilibrium_bounds(self) -> None:
        controller = QiFieldController(self.config(scales=1, modes=16, alphabet=8))
        state = controller.initial_state(1, dtype=torch.float64)
        packed = state.field.reshape(1, 9, 16, 1)
        packed[0, 0] = 1.0
        packed[0, 2] = controller.config.phi**-0.5
        equilibrium = controller.diagnostics(state)
        phi = controller.config.phi
        expected_rho = phi
        expected_q = phi**2 / (phi**2 + phi**-2)
        self.assertAlmostEqual(float(equilibrium.rho.item()), expected_rho, places=12)
        self.assertAlmostEqual(float(equilibrium.epsilon.item()), 0.0, places=12)
        self.assertAlmostEqual(float(equilibrium.q.item()), expected_q, places=12)
        self.assertAlmostEqual(float(equilibrium.q_max.item()), expected_q, places=12)
        self.assertAlmostEqual(float(equilibrium.chi.item()), 1.0, places=12)

        unit = controller.initial_state(1, dtype=torch.float64)
        unit.field.reshape(1, 9, 16, 1)[0, 0] = 1.0
        unit_metrics = controller.diagnostics(unit)
        expected_unit_q = 1.0 / (1.0 + phi**-2)
        self.assertAlmostEqual(float(unit_metrics.q.item()), expected_unit_q, places=12)
        self.assertTrue(bool(torch.all((unit_metrics.q >= 0) & (unit_metrics.q <= unit_metrics.q_max)).item()))
        self.assertTrue(bool(torch.all((unit_metrics.q_max >= 0) & (unit_metrics.q_max <= 1)).item()))
        self.assertTrue(bool(torch.all((unit_metrics.chi >= 0) & (unit_metrics.chi <= 1)).item()))

    def test_epsilon_iir_uses_tau_as_new_sample_weight(self) -> None:
        controller = QiFieldController(self.config(scales=1, modes=16, alphabet=8))
        state = controller.initial_state(1, dtype=torch.float64)
        packed = state.field.reshape(1, 9, 16, 1)
        # D=Y-phi*I is zero, while canonical epsilon=E_Y-phi E_I=1.
        packed[0, 0] = controller.config.phi
        packed[0, 2] = 1.0
        evolved = controller.evolve(state, steps=1)
        diagnostics = controller.diagnostics(evolved)
        self.assertAlmostEqual(float(diagnostics.epsilon.item()), 1.0, places=12)
        self.assertAlmostEqual(float(diagnostics.epsilon2_ema.item()), controller.config.epsilon_tau, places=12)
        self.assertAlmostEqual(controller.config.epsilon_tau, controller.config.phi**-1, places=12)

    def test_codebooks_are_distinct_and_round_trip_alignment_is_exact(self) -> None:
        controller = QiFieldController(self.config(scales=4, modes=32, alphabet=16))
        codebooks = controller.codebooks(dtype=torch.float64)
        self.assertEqual(tuple(codebooks.shape), (4, 16, 16, 2))
        self.assertEqual(len(set(controller.config.primes)), 4)
        self.assertEqual(len(QI_COMPONENT_ORDER), 9)
        self.assertFalse(torch.equal(codebooks[0], codebooks[1]))
        correlations = []
        for first in range(4):
            for second in range(first + 1, 4):
                same_symbol = codebooks[first, 3]
                other_symbol = codebooks[second, 3]
                correlations.append(float((same_symbol * other_symbol).sum().item() / controller.wave_mode_count))
        self.assertLess(max(abs(value) for value in correlations), 0.35)
        for scale in range(controller.scale_count):
            values = torch.arange(controller.wave_mode_count * 2, dtype=torch.float64).reshape(controller.wave_mode_count, 2)
            aligned = controller._align_active(values, scale)
            restored = controller._unalign_active(aligned, scale)
            torch.testing.assert_close(restored, values, rtol=0.0, atol=0.0)

    def test_source_trust_blocks_unstructured_wave_and_write_uses_one_minus_q(self) -> None:
        controller = QiFieldController(self.config(scales=1, modes=32, alphabet=8))
        empty = controller.initial_state(2)
        code = controller.codebook(0)
        wave = code[2].unsqueeze(0).repeat(2, 1, 1)
        wave[1] = torch.randn_like(wave[1])
        result = controller.sense_wave(empty, wave, return_result=True)
        self.assertGreater(float(result.source_trust[0]), 0.99)
        self.assertLess(float(result.source_trust[1]), controller.config.write_trust_floor)
        self.assertGreater(float(result.write_gate[0]), 0.99)
        self.assertEqual(float(result.write_gate[1]), 0.0)
        self.assertGreater(float(result.state.field[:, :, 0].abs().sum()), 0.0)
        self.assertEqual(float(result.state.field[:, :, 1].abs().sum()), 0.0)

        coherent = controller.sense_symbols(controller.initial_state(1), torch.tensor([2]))
        diagnostics = controller.diagnostics(coherent, structured_source=1.0)
        self.assertAlmostEqual(float(diagnostics.write_gate[0, 0]), 1.0 - float(diagnostics.q[0, 0]), places=6)
        self.assertNotAlmostEqual(float(diagnostics.write_gate[0, 0]), 1.0 - float(diagnostics.chi[0, 0]), places=4)
    def test_correct_wave_matches_symbol_correction(self) -> None:
        controller = QiFieldController(self.config(scales=2, modes=32, alphabet=8))
        state = controller.sense_symbols(
            controller.initial_state(2),
            torch.tensor([2, 5]),
        )
        target_symbols = torch.tensor([5, 1])
        target_wave = controller.codebook(0).index_select(0, target_symbols)

        symbol_state, symbol_energy = controller.correct(state, target_symbols)
        wave_state, wave_energy = controller.correct_wave(
            state,
            target_wave,
            correction_gain=1.0,
        )

        torch.testing.assert_close(symbol_state.field, wave_state.field, rtol=0.0, atol=0.0)
        torch.testing.assert_close(symbol_energy, wave_energy, rtol=0.0, atol=0.0)

    def test_correct_wave_validates_target_and_bounds_state(self) -> None:
        controller = QiFieldController(self.config(scales=2, modes=32, alphabet=8))
        state = controller.sense_symbols(controller.initial_state(1), torch.tensor([2]))
        target_wave = controller.codebook(0)[2].unsqueeze(0)

        with self.assertRaises(QiFieldError):
            controller.correct_wave(state, target_wave[:, :-1])

        nonfinite = target_wave.clone()
        nonfinite[0, 0, 0] = float("nan")
        with self.assertRaises(QiFieldError):
            controller.correct_wave(state, nonfinite)

        with self.assertRaises(QiFieldError):
            controller.correct_wave(state, target_wave.to(dtype=torch.int64))

        for invalid_gain in (-0.01, 1.01, float("nan"), float("inf")):
            with self.assertRaises(QiFieldError):
                controller.correct_wave(state, target_wave, correction_gain=invalid_gain)

        corrected, correction_energy = controller.correct_wave(
            state,
            target_wave * 1_000.0,
            correction_gain=1.0,
        )
        self.assertEqual(
            tuple(corrected.field.shape),
            (controller.config.scale_count, 9 * controller.config.mode_count, 1),
        )
        self.assertTrue(bool(torch.isfinite(corrected.field).all().item()))
        self.assertLessEqual(
            float(corrected.field.abs().max()),
            controller.config.physics.max_mode_amplitude + 1.0e-6,
        )
        self.assertTrue(bool(torch.isfinite(correction_energy).all().item()))


    def test_cross_scale_consolidation_requires_aligned_coherence_and_bootstraps_target(self) -> None:
        controller = QiFieldController(self.config(scales=3, modes=32, alphabet=8))
        source = controller.sense_symbols(controller.initial_state(1), torch.tensor([2]))
        before = controller.diagnostics(source)
        self.assertGreater(float(before.consolidation_gate[0, 0]), 0.0)
        consolidated_result = controller.consolidate(source, return_result=True)
        after = controller.diagnostics(consolidated_result.state)
        self.assertGreater(float(consolidated_result.consolidation_gate[0, 0]), 0.0)
        self.assertGreater(float(after.rho[1, 0]), 0.0)
        self.assertGreater(float(after.cross_scale_coherence[0, 0]), 0.99)
        self.assertGreaterEqual(float(after.j_scale[0, 0]), -1.0e-6)
        # The source symbol is demodulated, then rebound into the target
        # codebook; every active bank therefore decodes the same symbol.
        self.assertEqual(
            controller._metrics_raw(consolidated_result.state)["decoded_symbols"][:, 0].tolist()[:2],
            [2, 2],
        )
        emission = controller.emit(consolidated_result.state)
        self.assertTrue(bool(emission.available.item()))
        self.assertEqual(int(emission.symbols.item()), 2)

        positive = torch.ones(controller.wave_mode_count, dtype=torch.float64)
        negative = -positive
        opposed = self.differential_state(
            controller,
            [positive, negative, torch.zeros_like(positive)],
        )
        opposed_metrics = controller.diagnostics(opposed)
        self.assertLess(float(opposed_metrics.cross_scale_coherence[0, 0]), 1.0e-6)
        self.assertEqual(float(opposed_metrics.consolidation_gate[0, 0]), 0.0)
    def test_false_resonance_is_suppressed_against_one_scale(self) -> None:
        one = QiFieldController(self.config(scales=1, modes=32, alphabet=8))
        multi = QiFieldController(self.config(scales=2, modes=32, alphabet=8))
        source = multi.codebook(0, dtype=torch.float64)[3, :, 0]
        opposed_target = -multi.codebook(1, dtype=torch.float64)[3, :, 0]
        one_state = self.differential_state(one, [source])
        multi_state = self.differential_state(multi, [source, opposed_target])
        one_emission = one.emit(one_state)
        multi_emission = multi.emit(multi_state)
        self.assertTrue(bool(one_emission.available.item()))
        self.assertFalse(bool(multi_emission.available.item()))
        self.assertEqual(int(multi_emission.symbols.item()), -1)
        self.assertLess(float(multi_emission.read_gate.item()), multi.config.read_threshold)

    def test_matched_budget_collision_stream_is_not_worse(self) -> None:
        one = QiFieldController(self.config(scales=1, modes=32, alphabet=8))
        multi = QiFieldController(self.config(scales=2, modes=16, alphabet=8))
        self.assertEqual(one.scale_count * one.mode_count, multi.scale_count * multi.mode_count)
        first, collision, strength = 0, 1, 0.4
        one_codes = one.codebook(0, dtype=torch.float64)
        multi_codes = multi.codebook(0, dtype=torch.float64)
        one_wave = one_codes[first] + strength * one_codes[collision]
        multi_wave = multi_codes[first] + strength * multi_codes[collision]
        one_state = one.sense_wave(
            one.initial_state(1, dtype=torch.float64),
            one_wave.unsqueeze(0),
            structured_source=1.0,
        )
        multi_state = multi.sense_wave(
            multi.initial_state(1, dtype=torch.float64),
            multi_wave.unsqueeze(0),
            structured_source=1.0,
        )
        multi_state = multi.consolidate(multi_state)
        one_emission = one.emit(one_state)
        multi_emission = multi.emit(multi_state)
        # At equal total mode budget, both deterministic collision streams
        # retain the same top-symbol accuracy; multi-scale is not worse.
        self.assertTrue(bool(one_emission.available.item()))
        self.assertTrue(bool(multi_emission.available.item()))
        self.assertEqual(int(one_emission.symbols.item()), first)
        self.assertEqual(int(multi_emission.symbols.item()), first)

    def test_long_horizon_remains_finite_and_bounded(self) -> None:
        controller = QiFieldController(self.config(scales=2, modes=16, alphabet=8))
        state = controller.sense_symbols(controller.initial_state(1), torch.tensor([3]))
        state = controller.evolve(state, steps=10_000)
        self.assertTrue(bool(torch.isfinite(state.field).all().item()))
        self.assertLessEqual(float(state.field.abs().max()), controller.config.physics.max_mode_amplitude + 1.0e-6)
        diagnostics = controller.diagnostics(state)
        self.assertTrue(bool(torch.isfinite(diagnostics.q).all().item()))
        self.assertTrue(bool(torch.all((diagnostics.q >= 0) & (diagnostics.q <= diagnostics.q_max)).item()))

    def test_reset_semantics_are_explicit(self) -> None:
        controller = QiFieldController(self.config(scales=3, modes=16, alphabet=8))
        state = controller.sense_symbols(controller.initial_state(1), torch.tensor([1]))
        packed = state.field.reshape(3, 9, 16, 1)
        packed[1, 0] = 2.0
        packed[1, 8] = 0.5
        packed[:, 4:8] = 1.0
        cleared = controller.reset(state, preserve_memory=False)
        self.assertTrue(torch.equal(cleared.field, torch.zeros_like(cleared.field)))
        preserved = controller.reset(state, preserve_memory=True)
        preserved_parts = preserved.field.reshape(3, 9, 16, 1)
        self.assertTrue(torch.equal(preserved_parts[0], torch.zeros_like(preserved_parts[0])))
        self.assertGreater(float(preserved_parts[1, 0].abs().sum()), 0.0)
        self.assertAlmostEqual(float(preserved_parts[1, 8].mean()), 0.5, places=6)
        self.assertTrue(torch.equal(preserved_parts[:, 4:8], torch.zeros_like(preserved_parts[:, 4:8])))

    def test_in_memory_checkpoint_codec_round_trip_and_file_equivalence(self) -> None:
        controller = QiFieldController(self.config(scales=2, modes=16, alphabet=8))
        state = controller.consolidate(
            controller.sense_symbols(controller.initial_state(2), torch.tensor([4, 6]))
        )
        source = QiFieldState(state.field.detach().clone().requires_grad_(True))
        payload = controller.dump_state_bytes(source)
        self.assertIsInstance(payload, bytes)
        self.assertGreater(len(payload), 0)

        restored = controller.load_state_bytes(payload)
        self.assertFalse(restored.field.requires_grad)
        self.assertNotEqual(restored.field.data_ptr(), source.field.data_ptr())
        torch.testing.assert_close(restored.field, source.field.detach(), rtol=0.0, atol=0.0)
        restored.field.reshape(-1)[0] = 17.0
        self.assertNotEqual(float(restored.field.reshape(-1)[0]), float(source.field.detach().reshape(-1)[0]))

        for compatible_payload in (bytearray(payload), memoryview(payload)):
            compatible = controller.load_state_bytes(compatible_payload, device=None)
            torch.testing.assert_close(compatible.field, source.field.detach(), rtol=0.0, atol=0.0)

        restored64 = controller.load_state_bytes(payload, dtype=torch.float64)
        self.assertEqual(restored64.field.dtype, torch.float64)
        torch.testing.assert_close(restored64.field, source.field.detach().to(torch.float64), rtol=0.0, atol=0.0)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qi-field.pt"
            digest = controller.save(path, source)
            file_payload = path.read_bytes()
            self.assertEqual(file_payload, payload)
            self.assertEqual(digest, hashlib.sha256(file_payload).hexdigest())
            file_restored = controller.load(path)
            byte_restored = controller.load_state_bytes(file_payload)
            torch.testing.assert_close(file_restored.field, byte_restored.field, rtol=0.0, atol=0.0)

    def test_state_byte_codec_rejects_malformed_oversize_and_non_bytes(self) -> None:
        controller = QiFieldController(self.config(scales=1, modes=16, alphabet=8))
        for invalid in (True, False, None, 1, "bytes", object(), torch.tensor([1])):
            with self.assertRaises(QiFieldError):
                controller.load_state_bytes(invalid)
        for empty in (b"", bytearray(), memoryview(b"")):
            with self.assertRaises(QiFieldError):
                controller.load_state_bytes(empty)
        with self.assertRaises(QiFieldError):
            controller.load_state_bytes(bytes(64 * 1024 * 1024 + 1))
        with self.assertRaises(QiFieldError):
            controller.load_state_bytes(b"not a torch checkpoint")

        state = controller.initial_state(1)
        nonfinite = state.field.detach().clone()
        nonfinite.reshape(-1)[0] = float("nan")
        with self.assertRaises(QiFieldError):
            controller.dump_state_bytes(QiFieldState(nonfinite))

        payload = controller.dump_state_bytes(state)
        artifact = torch.load(io.BytesIO(payload), map_location="cpu", weights_only=True)
        artifact["field"] = artifact["field"].clone()
        artifact["field"].reshape(-1)[0] = float("nan")
        corrupt_stream = io.BytesIO()
        torch.save(artifact, corrupt_stream)
        with self.assertRaises(QiFieldError):
            controller.load_state_bytes(corrupt_stream.getvalue())

    def test_exact_checkpoint_restore_and_identity_rejection(self) -> None:
        controller = QiFieldController(self.config(scales=2, modes=16, alphabet=8))
        state = controller.consolidate(controller.sense_symbols(controller.initial_state(1), torch.tensor([4])))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qi-field.pt"
            digest = controller.save(path, state)
            restored = controller.load(path)
            self.assertEqual(len(digest), 64)
            torch.testing.assert_close(restored.field, state.field, rtol=0.0, atol=0.0)

            wrong = QiFieldController(self.config(scales=2, modes=16, alphabet=9))
            with self.assertRaises(QiFieldError):
                wrong.load(path)

            payload = torch.load(path, map_location="cpu", weights_only=True)
            payload["schema"] = "cassi.field-intelligence.state.v1"
            old_path = Path(directory) / "old.pt"
            torch.save(payload, old_path)
            with self.assertRaises(QiFieldError):
                controller.load(old_path)

            payload = torch.load(path, map_location="cpu", weights_only=True)
            payload["layout_id"] = "wrong-layout"
            wrong_path = Path(directory) / "wrong-layout.pt"
            torch.save(payload, wrong_path)
            with self.assertRaises(QiFieldError):
                controller.load(wrong_path)

    def test_explicit_profile_v3_checkpoint_is_independent_of_legacy_controller_state(self) -> None:
        profile = QiFlowProfile.from_defaults()
        state = QiFlowStateV3.create(profile, batch_lanes=1)
        state.field[0, 0, 0] = 0.125
        payload = dump_v3_state_bytes(state, profile)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qi-flow-v3.state"
            expected_hash = save_v3_checkpoint(path, state, profile)
            restored = load_v3_checkpoint(path, profile, device="cpu")
        self.assertEqual(restored.state_sha256(profile), expected_hash)
        torch.testing.assert_close(restored.field, state.field, rtol=0.0, atol=0.0)
        with self.assertRaises(PROFILE_MISMATCH):
            load_v3_state_bytes(payload[:-1], profile)

    def test_balance_conversion_preserves_density_and_reduces_imbalance(self) -> None:
        controller = QiFieldController(self.config(scales=3, modes=16, alphabet=8))
        torch.manual_seed(913)
        field = controller.initial_state(2).field
        parts = field.reshape(3, 9, 16, 2)
        parts[:, :4] = torch.randn_like(parts[:, :4])
        source = QiFieldState(field)

        converted = controller.convert_balance(source, rate=0.05, time_step=0.1)

        torch.testing.assert_close(
            converted.density_after,
            converted.density_before,
            rtol=2.0e-6,
            atol=2.0e-6,
        )
        self.assertLessEqual(
            float(converted.imbalance_l1_after.sum().item()),
            float(converted.imbalance_l1_before.sum().item()) + 2.0e-6,
        )
        self.assertGreater(float(converted.transferred_density.abs().sum().item()), 0.0)
        self.assertFalse(torch.equal(converted.state.field, source.field))
        self.assertTrue(torch.equal(source.field, field))

        for invalid_rate, invalid_step in ((-1.0, 0.1), (0.1, 0.0), (float("nan"), 0.1)):
            with self.assertRaises(QiFieldError):
                controller.convert_balance(source, rate=invalid_rate, time_step=invalid_step)



if __name__ == "__main__":
    unittest.main()
