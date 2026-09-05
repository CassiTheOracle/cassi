from __future__ import annotations

import dataclasses
import hashlib
import unittest
from dataclasses import replace

import torch

from cassi_organism import (
    ACTION_COMMITMENT_OFFSET,
    CassiOrganismConfig,
    CassiOrganismLawConfig,
    create_organism_state,
    dump_organism_state_bytes,
    organism_state_sha256,
)
from cassi_organism_law import (
    CassiAllLayerTeacherWeave,
    CassiFieldOrganism,
    CassiOrganismInput,
    CassiOrganismLawError,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState
from cassi_world_model import CassiWorldModel, CassiWorldModelConfig

MODEL_SHA = "a" * 64
RUNTIME_SHA = "b" * 64


class CassiOrganismLawTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(2468)
        self.controller = QiFieldController(
            QiFieldConfig(scale_count=2, mode_count=16, alphabet_size=260)
        )
        self.world_config = CassiWorldModelConfig(
            observation_dim=6,
            action_dim=3,
            mode_count=16,
            model_dim=8,
            latent_dim=4,
            hidden_dim=16,
            mlp_layers=1,
        )
        self.world_model = CassiWorldModel(self.world_config)
        self.config = CassiOrganismConfig.from_components(
            self.controller.config,
            self.world_config,
            action_horizon=8,
            shadow_branches=2,
            shadow_steps=4,
            history_capacity=8,
            history_width=12,
            action_population_capacity=4,
            attention_slots=16,
            theta_width=16,
            teacher_layer_count=4,
            teacher_layer_width=12,
        )

    def state(self, config: CassiOrganismConfig | None = None, qi: QiFieldState | None = None):
        selected = self.config if config is None else config
        return create_organism_state(
            selected,
            self.controller.initial_state(1) if qi is None else qi,
            self.world_model.initial_state(1),
            metadata={"identity": "organism-law-test"},
        )


    def test_ordered_cycle_conserves_density_attention_resources_and_prior(self) -> None:
        packed = torch.zeros(2, 9, 16, 1, dtype=torch.float32)
        packed[:, 0, :, 0] = 0.25
        state = self.state(qi=QiFieldState(packed.reshape(2, 9 * 16, 1)))
        before = state.arena.clone()
        result = CassiFieldOrganism(self.controller, self.config).step(
            state,
            CassiOrganismInput(
                observation=torch.linspace(-0.5, 0.5, 6),
                reward=0.3,
                resource_credit=0.2,
                unexpectedness=0.8,
                event_sha256="c" * 64,
            ),
        )
        self.assertTrue(torch.equal(state.arena, before))
        self.assertFalse(torch.equal(result.state.arena, state.arena))
        self.assertEqual(result.receipt.prior_state_sha256, organism_state_sha256(state, self.config))
        self.assertEqual(result.receipt.successor_state_sha256, organism_state_sha256(result.state, self.config))
        self.assertEqual(result.receipt.world_step, 1)
        self.assertLessEqual(result.receipt.density_conservation_residual, 1.0e-5)
        self.assertLessEqual(result.receipt.imbalance_l1_after, result.receipt.imbalance_l1_before + 1.0e-5)
        self.assertAlmostEqual(result.receipt.attention_sum_before, 1.0, places=6)
        self.assertAlmostEqual(result.receipt.attention_sum_after, 1.0, places=6)
        self.assertAlmostEqual(result.receipt.ledger.closure_residual, 0.0, places=5)
        self.assertGreater(result.receipt.ledger.total_work, 0.0)
        self.assertNotEqual(result.receipt.boundary_before, result.receipt.boundary_after)
        self.assertTrue(torch.all((result.state.z >= 0.0) & (result.state.z <= 1.0)))
        self.assertTrue(torch.equal(result.state.q, result.state.rho.square() / (
            result.state.rho.square() + self.controller.config.phi ** -2 + result.state.epsilon.square()
        ).clamp_min(torch.finfo(torch.float32).tiny)))

    def test_zero_resource_means_no_unfunded_state_transition(self) -> None:
        law = replace(
            self.config.law,
            initial_reserve=0.0,
            passive_dissipation=0.0,
        )
        config = replace(self.config, law=law)
        state = self.state(config)
        result = CassiFieldOrganism(self.controller, config).step(state)
        self.assertTrue(torch.equal(result.state.arena, state.arena))
        self.assertEqual(result.receipt.prior_state_sha256, result.receipt.successor_state_sha256)
        self.assertEqual(result.receipt.world_step, 0)
        self.assertEqual(result.receipt.action_population.computed_shadow_steps, 0)
        self.assertEqual(result.receipt.learning.reason, "resource-gated")
        self.assertEqual(result.receipt.ledger.total_work, 0.0)
        self.assertEqual(result.receipt.ledger.reserve_after, 0.0)

    def test_boundary_symbol_is_the_only_observation_source_and_updates_controls_once(self) -> None:
        state = self.state()
        before = state.arena.clone()
        symbol = ord("A")
        value = CassiOrganismInput(
            boundary_symbol=symbol,
            resource_credit=0.5,
            teacher=self.teacher(),
        )
        organism = CassiFieldOrganism(self.controller, self.config)

        first = organism.step(state, value)
        replay = organism.step(state, value)

        expected_wave = self.controller.codebook(
            0, device="cpu", dtype=torch.float32
        )[symbol : symbol + 1]
        self.assertTrue(torch.equal(state.arena, before))
        self.assertTrue(torch.equal(first.state.arena, replay.state.arena))
        self.assertEqual(first.receipt.to_bytes(), replay.receipt.to_bytes())
        self.assertEqual(
            first.receipt.successor_state_sha256,
            organism_state_sha256(first.state, self.config),
        )
        self.assertEqual(first.receipt.boundary_symbol, symbol)
        self.assertEqual(
            first.receipt.boundary_wave_sha256,
            hashlib.sha256(expected_wave.contiguous().numpy().tobytes()).hexdigest(),
        )
        self.assertEqual(first.receipt.language_step_before, 0)
        self.assertEqual(first.receipt.language_step_after, 1)
        self.assertFalse(torch.equal(first.state.qi, state.qi))
        self.assertFalse(torch.equal(first.state.h, state.h))
        self.assertFalse(torch.equal(first.state.m, state.m))

    def test_boundary_rejects_invalid_or_unfunded_inputs_without_mutating_state(self) -> None:
        organism = CassiFieldOrganism(self.controller, self.config)
        for bad_symbol in (-1, 260, True, 1.5, "A"):
            state = self.state()
            before = state.arena.clone()
            with self.assertRaises(CassiOrganismLawError):
                organism.step(state, CassiOrganismInput(boundary_symbol=bad_symbol))
            self.assertTrue(torch.equal(state.arena, before))

        state = self.state()
        before = state.arena.clone()
        with self.assertRaisesRegex(CassiOrganismLawError, "arbitrary observation"):
            organism.step(
                state,
                CassiOrganismInput(
                    boundary_symbol=ord("A"),
                    observation=torch.zeros(self.config.world_observation_dim),
                ),
            )
        self.assertTrue(torch.equal(state.arena, before))

        state = self.state()
        before = state.arena.clone()
        tampered_teacher = dataclasses.replace(
            self.teacher(),
            capture_sha256="c" * 64,
        )
        with self.assertRaisesRegex(CassiOrganismLawError, "capture hash"):
            organism.step(
                state,
                CassiOrganismInput(
                    boundary_symbol=ord("A"),
                    teacher=tampered_teacher,
                ),
            )
        self.assertTrue(torch.equal(state.arena, before))

        empty_law = replace(
            self.config.law,
            initial_reserve=0.0,
            passive_dissipation=0.0,
        )
        empty_config = replace(self.config, law=empty_law)
        empty_state = self.state(empty_config)
        empty_before = empty_state.arena.clone()
        with self.assertRaisesRegex(CassiOrganismLawError, "resource_exhausted"):
            CassiFieldOrganism(self.controller, empty_config).step(
                empty_state,
                CassiOrganismInput(boundary_symbol=ord("A")),
            )
        self.assertTrue(torch.equal(empty_state.arena, empty_before))

    def test_external_credit_is_bounded_and_overflow_is_exported(self) -> None:
        law = replace(self.config.law, initial_reserve=0.0, reserve_capacity=0.1)
        config = replace(self.config, law=law)
        state = self.state(config)
        result = CassiFieldOrganism(self.controller, config).step(
            state, CassiOrganismInput(resource_credit=10.0)
        )
        self.assertGreater(result.receipt.ledger.overflow_exported, 9.0)
        self.assertTrue(torch.all(result.state.a <= law.reserve_capacity))
        self.assertAlmostEqual(result.receipt.ledger.closure_residual, 0.0, places=5)

    def test_credit_fill_with_nonzero_reserve_stays_within_capacity(self) -> None:
        law = replace(
            self.config.law,
            initial_reserve=0.1,
            reserve_capacity=0.4,
            passive_dissipation=0.0,
            field_step_cost=0.0,
            history_write_cost=0.0,
            model_step_cost=0.0,
            shadow_step_cost=0.0,
            action_step_cost=0.0,
            attention_step_cost=0.0,
            plasticity_step_cost=0.0,
        )
        config = replace(self.config, law=law)
        result = CassiFieldOrganism(self.controller, config).step(
            self.state(config),
            CassiOrganismInput(resource_credit=10.0),
        )

        self.assertTrue(torch.all(result.state.a <= law.reserve_capacity))
        self.assertAlmostEqual(
            result.receipt.ledger.external_credit_stored,
            config.scale_count * (law.reserve_capacity - law.initial_reserve),
            places=6,
        )
        self.assertAlmostEqual(result.receipt.ledger.closure_residual, 0.0, places=7)

    def teacher(self) -> CassiAllLayerTeacherWeave:
        return CassiAllLayerTeacherWeave.from_layers(
            tuple(torch.linspace(-1.0, 1.0, 12) + index for index in range(4)),
            source_model_sha256=MODEL_SHA,
            source_runtime_sha256=RUNTIME_SHA,
            token_index=7,
        )

    def test_every_teacher_layer_is_consumed_stop_gradient_and_not_checkpointed(self) -> None:
        teacher = self.teacher()
        state = self.state()
        organism = CassiFieldOrganism(self.controller, self.config)
        with_teacher = organism.step(
            state,
            CassiOrganismInput(observation=torch.ones(6), unexpectedness=0.8, teacher=teacher),
        )
        without_teacher = organism.step(
            state,
            CassiOrganismInput(observation=torch.ones(6), unexpectedness=0.8),
        )
        receipt = with_teacher.receipt.teacher
        self.assertTrue(receipt.consumed)
        self.assertEqual(receipt.layer_indices, (0, 1, 2, 3))
        self.assertEqual(len(receipt.layer_sha256), 4)
        self.assertEqual(receipt.capture_sha256, teacher.capture_sha256)
        self.assertFalse(receipt.raw_teacher_persisted)
        self.assertTrue(all(not layer.requires_grad and layer.device.type == "cpu" for layer in teacher.layer_vectors))
        self.assertFalse(torch.equal(with_teacher.state.y, without_teacher.state.y))
        self.assertFalse(torch.equal(with_teacher.state.e_Theta, without_teacher.state.e_Theta))
        checkpoint = dump_organism_state_bytes(with_teacher.state, self.config)
        self.assertNotIn(teacher.capture_sha256.encode("ascii"), checkpoint)
        self.assertNotIn(_first_layer_bytes(teacher), checkpoint)

    def test_teacher_weave_rejects_missing_or_tampered_layers(self) -> None:
        teacher = self.teacher()
        missing = dataclasses.replace(teacher, layer_vectors=teacher.layer_vectors[:-1])
        with self.assertRaisesRegex(CassiOrganismLawError, "every layer"):
            CassiFieldOrganism(self.controller, self.config).step(
                self.state(), CassiOrganismInput(teacher=missing)
            )
        wrong_width = dataclasses.replace(
            teacher,
            layer_vectors=(teacher.layer_vectors[0][:-1], *teacher.layer_vectors[1:]),
        )
        with self.assertRaisesRegex(CassiOrganismLawError, "configured width"):
            CassiFieldOrganism(self.controller, self.config).step(
                self.state(), CassiOrganismInput(teacher=wrong_width)
            )
        changed = list(teacher.layer_vectors)
        changed[2] = changed[2].clone()
        changed[2][0] += 1.0
        tampered = dataclasses.replace(teacher, layer_vectors=tuple(changed))
        with self.assertRaisesRegex(CassiOrganismLawError, "capture hash mismatch"):
            CassiFieldOrganism(self.controller, self.config).step(
                self.state(), CassiOrganismInput(teacher=tampered)
            )

    def test_shadow_bands_cover_population_and_action_comes_from_commitment(self) -> None:
        law = replace(
            self.config.law,
            commitment_threshold=0.2,
            release_threshold=0.1,
        )
        config = replace(self.config, law=law)
        organism = CassiFieldOrganism(self.controller, config)
        state = self.state(config)
        evaluated: set[int] = set()
        enacted = None
        committed = None
        for _ in range(12):
            result = organism.step(
                state,
                CassiOrganismInput(
                    observation=torch.linspace(-1.0, 1.0, 6),
                    reward=0.5,
                    resource_credit=0.5,
                    unexpectedness=0.8,
                ),
            )
            evaluated.update(result.receipt.action_population.evaluated_candidates)
            state = result.state
            if result.action is not None:
                enacted = result.action
                committed = result.receipt.action_population.committed_candidate
                break
        self.assertEqual(evaluated, set(range(config.action_population_capacity)))
        self.assertIsNotNone(enacted)
        self.assertIsNotNone(committed)
        self.assertTrue(torch.equal(state.u, enacted.squeeze(0)))
        self.assertGreaterEqual(
            float(state.p[committed, config.action_width + ACTION_COMMITMENT_OFFSET].item()),
            law.release_threshold,
        )

    def test_external_action_population_is_evaluated_and_requires_stable_candidates(self) -> None:
        law = replace(
            self.config.law,
            commitment_threshold=0.2,
            release_threshold=0.1,
        )
        config = replace(self.config, law=law)
        organism = CassiFieldOrganism(self.controller, config)
        state = self.state(config)
        candidates = torch.stack(
            (
                torch.full((config.action_horizon, config.world_action_dim), 0.35),
                torch.full((config.action_horizon, config.world_action_dim), -0.05),
                torch.full((config.action_horizon, config.world_action_dim), 0.15),
            )
        )
        first = organism.step(
            state,
            CassiOrganismInput(
                candidate_actions=candidates,
                resource_credit=0.5,
            ),
        )
        changed = organism.step(
            first.state,
            CassiOrganismInput(
                candidate_actions=candidates + 0.1,
                resource_credit=0.5,
            ),
        )
        commitment = changed.state.p[
            :3, config.action_width + ACTION_COMMITMENT_OFFSET
        ]
        self.assertLessEqual(float(commitment.max().item()), law.time_step + 1.0e-6)
        state = changed.state
        result = changed
        stable = candidates + 0.1
        for _ in range(4):
            result = organism.step(
                state,
                CassiOrganismInput(
                    candidate_actions=stable,
                    resource_credit=0.5,
                ),
            )
            state = result.state
            if result.action is not None:
                break
        self.assertEqual(result.receipt.action_population.evaluated_candidates, (0, 1, 2))
        self.assertIsNotNone(result.receipt.action_population.committed_candidate)
        self.assertIsNotNone(result.action)
        committed = result.receipt.action_population.committed_candidate
        self.assertTrue(torch.equal(result.action.squeeze(0), stable[committed]))

    def test_learning_is_bounded_matured_and_holdout_gated(self) -> None:
        law = replace(
            self.config.law,
            unexpected_threshold=0.05,
            theta_prediction_rate=0.05,
            theta_outcome_rate=0.05,
            theta_step_bound=0.05,
        )
        config = replace(self.config, law=law)
        organism = CassiFieldOrganism(self.controller, config)
        state = self.state(config)
        accepted = False
        for _ in range(8):
            prior_theta = state.Theta.clone()
            result = organism.step(
                state,
                CassiOrganismInput(
                    observation=torch.linspace(-0.8, 0.8, 6),
                    reward=1.0,
                    resource_credit=0.5,
                    unexpectedness=1.0,
                ),
            )
            self.assertLessEqual(
                float((result.state.Theta - prior_theta).abs().max().item()),
                max(law.theta_step_bound, 0.5) + 1.0e-6,
            )
            self.assertTrue(torch.all(result.state.Theta.abs() <= law.theta_absolute_bound))
            accepted |= result.receipt.learning.accepted
            state = result.state
        self.assertTrue(accepted)
        self.assertGreater(float(state.Theta[-2:].max().item()), 0.0)

    def test_zero_cost_operations_are_free_not_disabled(self) -> None:
        free_law = replace(
            self.config.law,
            initial_reserve=0.0,
            passive_dissipation=0.0,
            field_step_cost=0.0,
            history_write_cost=0.0,
            model_step_cost=0.0,
            shadow_step_cost=0.0,
            action_step_cost=0.0,
            attention_step_cost=0.0,
            plasticity_step_cost=0.0,
        )
        config = replace(self.config, shadow_branches=2, shadow_steps=3, law=free_law)
        packed = torch.zeros(2, 9, 16, 1, dtype=torch.float32)
        packed[:, 0, :, 0] = 0.25
        state = self.state(config, QiFieldState(packed.reshape(2, 9 * 16, 1)))

        result = CassiFieldOrganism(self.controller, config).step(
            state,
            CassiOrganismInput(observation=torch.linspace(-0.5, 0.5, 6)),
        )

        self.assertEqual(result.receipt.world_step, 1)
        self.assertEqual(result.receipt.action_population.computed_shadow_steps, 6)
        self.assertEqual(result.receipt.ledger.total_work, 0.0)
        self.assertEqual(result.receipt.ledger.reserve_after, 0.0)
        self.assertFalse(torch.equal(result.state.qi, state.qi))
        self.assertFalse(torch.equal(result.state.h, state.h))


    def test_same_state_and_input_produce_identical_successor_and_receipt(self) -> None:
        state = self.state()
        value = CassiOrganismInput(
            observation=torch.linspace(-0.3, 0.3, 6),
            reward=-0.2,
            resource_credit=0.1,
            unexpectedness=0.4,
            teacher=self.teacher(),
        )
        organism = CassiFieldOrganism(self.controller, self.config)
        first = organism.step(state, value)
        second = organism.step(state, value)
        self.assertTrue(torch.equal(first.state.arena, second.state.arena))
        self.assertEqual(first.receipt.to_bytes(), second.receipt.to_bytes())


def _first_layer_bytes(teacher: CassiAllLayerTeacherWeave) -> bytes:
    return teacher.layer_vectors[0].numpy().tobytes()


if __name__ == "__main__":
    unittest.main()
