import hashlib
import unittest

import torch

from cassi_conscious_field import (
    CassiConsciousField,
    ConsciousFieldConfig,
    tensor_wave_sha256,
)
from cassi_world_model import (
    CassiTrajectoryBatch,
    CassiWorldModel,
    CassiWorldModelConfig,
)
from cassi_conscious_protocol import ActorClass, EventKind, RealityStatus, create_event
from cassi_conscious_world import CassiConsciousWorldBridge, CassiConsciousWorldError
from cassi_modal_torch import CassiModalConfig
from cassi_qi_field import QiFieldConfig, QiFieldController


class SpyWorldModel(CassiWorldModel):
    def __init__(self, config: CassiWorldModelConfig) -> None:
        super().__init__(config)
        self.imagine_calls = 0
        self.observe_calls = 0

    def imagine(self, *args: object, **kwargs: object):
        self.imagine_calls += 1
        return super().imagine(*args, **kwargs)

    def observe(self, *args: object, **kwargs: object):
        self.observe_calls += 1
        return super().observe(*args, **kwargs)


class MutatingWorldModel(SpyWorldModel):
    def __init__(self, config: CassiWorldModelConfig) -> None:
        super().__init__(config)
        self.fail_imagine = False
        self.fail_observe = False

    @staticmethod
    def _mutate_state(state: object) -> None:
        state.field.add_(1.0)
        state.stochastic.mul_(0.0)
        state.step.add_(7)

    def imagine(self, actions: torch.Tensor, initial_state: object, **kwargs: object):
        actions.add_(3.0)
        self._mutate_state(initial_state)
        if self.fail_imagine:
            raise RuntimeError("malicious imagination failure")
        return super().imagine(actions, initial_state, **kwargs)

    def observe(self, batch: CassiTrajectoryBatch, initial_state: object, **kwargs: object):
        batch.observations.add_(2.0)
        batch.actions.mul_(0.0)
        batch.rewards.add_(1.0)
        batch.continues.mul_(0.0)
        self._mutate_state(initial_state)
        if self.fail_observe:
            raise RuntimeError("malicious observation failure")
        return super().observe(batch, initial_state, **kwargs)


class CassiConsciousWorldBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(17)
        model_config = CassiWorldModelConfig(
            observation_dim=3,
            action_dim=2,
            reward_dim=1,
            mode_count=2,
            latent_dim=3,
            model_dim=8,
            hidden_dim=8,
            mlp_layers=1,
            min_std=0.1,
            max_std=0.5,
            modal=CassiModalConfig(
                retained_weight=0.8,
                phi=1.61803398875,
                dt=0.002,
                omega2=8.0,
                coupling=0.5,
                steps_per_layer=1,
            ),
        )
        self.model = SpyWorldModel(model_config)
        controller = QiFieldController(
            QiFieldConfig(
                mode_count=16,
                alphabet_size=260,
                read_threshold=1e-9,
                emission_floor=1e-9,
            )
        )
        self.field = CassiConsciousField(controller, ConsciousFieldConfig())
        self.root_state = self.field.initial_state(dtype=torch.float32)
        self.world_state = self.model.initial_state(1)
        self.bridge = CassiConsciousWorldBridge(self.model, "a" * 64, self.field)
        self.actions = torch.tensor([[[0.2, -0.1], [0.1, 0.3]]], dtype=torch.float32)

    def local_intent(self) -> object:
        return create_event(
            sequence=1,
            kind=EventKind.ACTION_INTENT,
            reality_status=RealityStatus.AGENT_INTENT,
            actor=ActorClass.LOCAL_AGENT,
            payload=b"test-action",
            source_id="test",
        )

    def test_constructor_and_input_validation(self) -> None:
        with self.assertRaises(CassiConsciousWorldError):
            CassiConsciousWorldBridge(object(), "a" * 64, self.field)
        with self.assertRaises(CassiConsciousWorldError):
            CassiConsciousWorldBridge(self.model, "A" * 64, self.field)
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.imagine_consequence(
                self.local_intent(),
                torch.zeros((2, 2, 2)),
                self.world_state,
                self.root_state,
                sequence=2,
                imagination_steps=1,
            )
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.project_actual_consequence(
                torch.zeros((1, 2, 3)),
                torch.zeros((1, 2, 1)),
                torch.tensor([[float("nan"), 0.5]]),
                self.root_state,
            )

    def test_configured_resource_bounds_reject_bool_and_hard_overbounds(self) -> None:
        self.assertEqual(self.bridge.max_action_horizon, 64)
        self.assertEqual(self.bridge.max_batch_size, 1)
        configured = CassiConsciousWorldBridge(
            self.model,
            "a" * 64,
            self.field,
            max_action_horizon=2,
            max_batch_size=1,
        )
        self.assertEqual(configured.max_action_horizon, 2)
        with self.assertRaises(CassiConsciousWorldError):
            configured.imagine_consequence(
                self.local_intent(),
                torch.zeros((1, 3, 2)),
                self.world_state,
                self.root_state,
                sequence=2,
                imagination_steps=1,
            )
        self.assertEqual(self.model.imagine_calls, 0)

        for kwargs in (
            {"max_action_horizon": True},
            {"max_action_horizon": 65},
            {"max_action_horizon": 0},
            {"max_batch_size": True},
            {"max_batch_size": 2},
            {"max_batch_size": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(CassiConsciousWorldError):
                CassiConsciousWorldBridge(
                    self.model,
                    "a" * 64,
                    self.field,
                    **kwargs,
                )

    def test_overbounds_shapes_and_nonfinite_values_reject_before_model_calls(self) -> None:
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.imagine_consequence(
                self.local_intent(),
                torch.zeros((1, 65, 2)),
                self.world_state,
                self.root_state,
                sequence=2,
                imagination_steps=1,
            )
        self.assertEqual(self.model.imagine_calls, 0)

        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.imagine_consequence(
                self.local_intent(),
                torch.zeros((1, 2, 3)),
                self.world_state,
                self.root_state,
                sequence=2,
                imagination_steps=1,
            )
        self.assertEqual(self.model.imagine_calls, 0)

        batch_actions = torch.zeros((2, 2, 2))
        batch_observations = torch.zeros((2, 2, 3))
        batch_rewards = torch.zeros((2, 2, 1))
        batch_continues = torch.zeros((2, 2))
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.observe_actual(
                batch_observations,
                batch_actions,
                batch_rewards,
                batch_continues,
                self.world_state,
            )
        self.assertEqual(self.model.observe_calls, 0)

        mismatched_rewards = torch.zeros((1, 1, 1))
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.observe_actual(
                torch.zeros((1, 2, 3)),
                self.actions,
                mismatched_rewards,
                torch.zeros((1, 2)),
                self.world_state,
            )
        self.assertEqual(self.model.observe_calls, 0)

        nonfinite_actions = self.actions.clone()
        nonfinite_actions[0, 0, 0] = float("inf")
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.imagine_consequence(
                self.local_intent(),
                nonfinite_actions,
                self.world_state,
                self.root_state,
                sequence=2,
                imagination_steps=1,
            )
        self.assertEqual(self.model.imagine_calls, 0)

        nonfinite_observations = torch.zeros((1, 2, 3))
        nonfinite_observations[0, 1, 1] = float("nan")
        with self.assertRaises(CassiConsciousWorldError):
            self.bridge.observe_actual(
                nonfinite_observations,
                self.actions,
                torch.zeros((1, 2, 1)),
                torch.zeros((1, 2)),
                self.world_state,
            )
        self.assertEqual(self.model.observe_calls, 0)

    def test_malicious_model_cannot_mutate_live_inputs_on_success_or_failure(self) -> None:
        model = MutatingWorldModel(self.model.config)
        bridge = CassiConsciousWorldBridge(model, "b" * 64, self.field)
        world_state = model.initial_state(1)
        actions = self.actions.clone()
        world_snapshot = tuple(value.clone() for value in (
            world_state.field,
            world_state.stochastic,
            world_state.step,
        ))
        action_snapshot = actions.clone()

        result = bridge.imagine_consequence(
            self.local_intent(),
            actions,
            world_state,
            self.root_state,
            sequence=17,
            imagination_steps=2,
        )
        self.assertTrue(torch.equal(actions, action_snapshot))
        for value, snapshot in zip(
            (world_state.field, world_state.stochastic, world_state.step),
            world_snapshot,
            strict=True,
        ):
            self.assertTrue(torch.equal(value, snapshot))
        self.assertNotEqual(
            result.imagined_world_state.field.data_ptr(),
            world_state.field.data_ptr(),
        )
        self.assertNotEqual(
            result.output.final_state.field.data_ptr(),
            result.imagined_world_state.field.data_ptr(),
        )

        observations = torch.tensor([[[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]]])
        rewards = torch.tensor([[[0.2], [0.4]]])
        continues = torch.tensor([[0.8, 0.7]])
        observation_snapshot = observations.clone()
        reward_snapshot = rewards.clone()
        continue_snapshot = continues.clone()
        observed_state = bridge.observe_actual(
            observations,
            actions,
            rewards,
            continues,
            world_state,
        )
        self.assertTrue(torch.equal(observations, observation_snapshot))
        self.assertTrue(torch.equal(rewards, reward_snapshot))
        self.assertTrue(torch.equal(continues, continue_snapshot))
        for value, snapshot in zip(
            (world_state.field, world_state.stochastic, world_state.step),
            world_snapshot,
            strict=True,
        ):
            self.assertTrue(torch.equal(value, snapshot))
        self.assertNotEqual(
            observed_state.field.data_ptr(),
            world_state.field.data_ptr(),
        )

        model.fail_imagine = True
        failed_world_snapshot = tuple(value.clone() for value in (
            world_state.field,
            world_state.stochastic,
            world_state.step,
        ))
        failed_action_snapshot = actions.clone()
        with self.assertRaises(RuntimeError):
            bridge.imagine_consequence(
                self.local_intent(),
                actions,
                world_state,
                self.root_state,
                sequence=17,
                imagination_steps=2,
            )
        self.assertTrue(torch.equal(actions, failed_action_snapshot))
        for value, snapshot in zip(
            (world_state.field, world_state.stochastic, world_state.step),
            failed_world_snapshot,
            strict=True,
        ):
            self.assertTrue(torch.equal(value, snapshot))

        model.fail_imagine = False
        model.fail_observe = True
        failed_observation_snapshot = observations.clone()
        failed_reward_snapshot = rewards.clone()
        failed_continue_snapshot = continues.clone()
        failed_world_snapshot = tuple(value.clone() for value in (
            world_state.field,
            world_state.stochastic,
            world_state.step,
        ))
        with self.assertRaises(RuntimeError):
            bridge.observe_actual(
                observations,
                actions,
                rewards,
                continues,
                world_state,
            )
        self.assertTrue(torch.equal(observations, failed_observation_snapshot))
        self.assertTrue(torch.equal(rewards, failed_reward_snapshot))
        self.assertTrue(torch.equal(continues, failed_continue_snapshot))
        for value, snapshot in zip(
            (world_state.field, world_state.stochastic, world_state.step),
            failed_world_snapshot,
            strict=True,
        ):
            self.assertTrue(torch.equal(value, snapshot))


    def test_projection_is_deterministic_sensitive_and_bounded(self) -> None:
        observations = torch.tensor([[[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]]])
        rewards = torch.tensor([[[0.2], [0.4]]])
        continues = torch.tensor([[0.8, 0.7]])
        first = self.bridge.project_actual_consequence(observations, rewards, continues, self.root_state)
        second = self.bridge.project_actual_consequence(observations, rewards, continues, self.root_state)
        changed = self.bridge.project_actual_consequence(observations + 0.1, rewards, continues, self.root_state)
        self.assertTrue(torch.equal(first, second))
        self.assertFalse(torch.equal(first, changed))
        self.assertLessEqual(float(torch.linalg.vector_norm(first, dim=-1).amax()), 1.000001)

    def test_imagination_is_read_only_and_action_sensitive(self) -> None:
        parameter_snapshot = [parameter.detach().clone() for parameter in self.model.parameters()]
        root_snapshot = self.root_state.field.clone()
        world_snapshot = self.world_state.field.clone()
        first = self.bridge.imagine_consequence(self.local_intent(), self.actions, self.world_state, self.root_state, sequence=17, imagination_steps=2)
        second = self.bridge.imagine_consequence(self.local_intent(), self.actions, self.world_state, self.root_state, sequence=17, imagination_steps=2)
        changed = self.bridge.imagine_consequence(self.local_intent(), self.actions + 0.2, self.world_state, self.root_state, sequence=17, imagination_steps=2)
        self.assertTrue(torch.equal(first.wave, second.wave))
        self.assertFalse(torch.equal(first.wave, changed.wave))
        self.assertTrue(torch.equal(self.root_state.field, root_snapshot))
        self.assertTrue(torch.equal(self.world_state.field, world_snapshot))
        for parameter, snapshot in zip(self.model.parameters(), parameter_snapshot, strict=True):
            self.assertTrue(torch.equal(parameter, snapshot))
            self.assertIsNone(parameter.grad)


    def test_imagined_world_state_is_not_a_live_transition(self) -> None:
        result = self.bridge.imagine_consequence(
            self.local_intent(),
            self.actions,
            self.world_state,
            self.root_state,
            sequence=17,
            imagination_steps=2,
        )
        self.assertTrue(hasattr(result, "imagined_world_state"))
        self.assertFalse(hasattr(result, "next_world_state"))
        self.assertFalse(hasattr(result, "final_world_state"))
        observations = torch.tensor([[[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]]])
        rewards = torch.tensor([[[0.2], [0.4]]])
        continues = torch.tensor([[0.8, 0.7]])
        actual = self.bridge.observe_actual(
            observations,
            self.actions,
            rewards,
            continues,
            self.world_state,
        )
        valid = torch.ones((1, 2), dtype=torch.bool)
        expected_batch = CassiTrajectoryBatch(
            observations,
            self.actions,
            rewards,
            continues,
            valid,
            torch.zeros_like(valid),
        )
        with torch.no_grad():
            expected = self.model.observe(
                expected_batch,
                self.world_state.clone(),
                sample=False,
            ).final_state
        self.assertTrue(torch.equal(actual.field, expected.field))

    def test_exact_predicted_consequence_confirms_and_altered_consequence_contradicts(self) -> None:
        result = self.bridge.imagine_consequence(self.local_intent(), self.actions, self.world_state, self.root_state, sequence=17, imagination_steps=2)
        predicted_continues = torch.sigmoid(result.output.continue_logits)
        exact_event = create_event(
            sequence=18,
            kind=EventKind.ACTION_OUTCOME,
            reality_status=RealityStatus.OBSERVED_REALITY,
            actor=ActorClass.ENVIRONMENT,
            payload=b"exact field prediction",
            source_id="sensor:test",
            parent_event_id=self.local_intent().event_id,
            boundary_wave_sha256=tensor_wave_sha256(result.branch.predicted_wave),
        )
        confirmed = self.bridge.reconcile_consequence(
            self.root_state,
            result.branch,
            exact_event,
            result.branch.predicted_wave,
        )
        self.assertEqual(confirmed.branch_status.value, "confirmed")
        self.assertTrue(torch.equal(confirmed.actual.input_wave, result.branch.predicted_wave))
        self.assertNotEqual(
            confirmed.actual.input_wave.data_ptr(),
            result.branch.predicted_wave.data_ptr(),
        )
        altered_event, altered_wave = self.bridge.create_observed_consequence_event(
            self.local_intent(), result.output.observation_mean + 0.2, result.output.reward_mean, predicted_continues, self.root_state, sequence=18, source_id="sensor:test"
        )
        contradicted = self.bridge.reconcile_consequence(self.root_state, result.branch, altered_event, altered_wave)
        self.assertEqual(contradicted.branch_status.value, "contradicted")

    def test_observe_actual_is_deterministic_and_separate_from_qi(self) -> None:
        observations = torch.tensor([[[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]]])
        rewards = torch.tensor([[[0.2], [0.4]]])
        continues = torch.tensor([[0.8, 0.7]])
        root_snapshot = self.root_state.field.clone()
        first = self.bridge.observe_actual(observations, self.actions, rewards, continues, self.world_state)
        second = self.bridge.observe_actual(observations, self.actions, rewards, continues, self.world_state)
        self.assertTrue(torch.equal(first.field, second.field))
        self.assertTrue(torch.equal(first.stochastic, second.stochastic))
        self.assertTrue(torch.equal(self.root_state.field, root_snapshot))


if __name__ == "__main__":
    unittest.main()
