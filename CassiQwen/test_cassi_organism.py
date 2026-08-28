from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

import torch

from cassi_organism import (
    ACTION_VIABILITY_OFFSET,
    ORGANISM_CHECKPOINT_SCHEMA,
    ORGANISM_SECTOR_ORDER,
    CassiOrganismConfig,
    CassiOrganismLawConfig,
    CassiOrganismError,
    CassiOrganismLayout,
    CassiOrganismState,
    create_organism_state,
    dump_organism_state_bytes,
    load_organism_state,
    load_organism_state_bytes,
    organism_state_sha256,
    qi_state_from_organism,
    save_organism_state,
    successor_organism_state,
    world_state_from_organism,
)
from cassi_qi_field import QI_COMPONENT_ORDER, QI_FIELD_STATE_SCHEMA, QiFieldConfig, QiFieldController, QiFieldState
from cassi_world_model import CassiWorldModel, CassiWorldModelConfig, CassiWorldModelState


class CassiOrganismStateTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(83)
        self.qi_controller = QiFieldController(QiFieldConfig(scale_count=3, mode_count=16))
        self.world_model = CassiWorldModel(
            CassiWorldModelConfig(
                observation_dim=3,
                action_dim=2,
                mode_count=2,
                latent_dim=3,
                model_dim=8,
                hidden_dim=8,
                mlp_layers=1,
            )
        )
        self.config = CassiOrganismConfig.from_components(
            self.qi_controller.config,
            self.world_model.config,
            action_horizon=8,
            shadow_branches=2,
            shadow_steps=3,
            history_capacity=5,
            action_population_capacity=3,
            attention_slots=17,
            theta_width=19,
            teacher_layer_count=4,
        )
        qi = self.qi_controller.initial_state(batch_size=1, dtype=torch.float32)
        packed = qi.field.reshape(3, 9, 16, 1)
        for component in range(9):
            packed[:, component, :, 0] = (component + 1) * 1.0e-3
        world = self.world_model.initial_state(1)
        world = CassiWorldModelState(
            torch.linspace(-0.1, 0.1, 16, dtype=torch.float32).reshape(16, 1),
            torch.tensor([[0.2, -0.3, 0.4]], dtype=torch.float32),
            torch.tensor([7], dtype=torch.int64),
        )
        self.qi = qi
        self.world = world
        self.metadata = b'{"active_commitment_event_id":null,"config_fingerprint":"fixture","pending":null,"schema":"fixture.v1"}'
        self.state = create_organism_state(self.config, qi, world, metadata=self.metadata)

    def test_one_arena_owns_all_typed_nonoverlapping_sectors(self) -> None:
        self.assertEqual(
            [field.name for field in fields(CassiOrganismState)],
            ["_arena", "config_fingerprint", "layout", "metadata"],
        )
        self.assertEqual(self.state.arena.dtype, torch.float32)
        self.assertEqual(tuple(self.state.arena.shape), self.config.arena_shape)
        layout = CassiOrganismLayout.build(self.config)
        self.assertEqual(tuple(entry.name for entry in layout.ranges), ORGANISM_SECTOR_ORDER)
        occupied: set[int] = set()
        for entry in layout.ranges:
            sector = self.state.sector(self.config, entry.name)
            self.assertEqual(tuple(sector.shape), entry.logical_shape)
            indices = set(range(entry.start_tile, entry.stop_tile))
            self.assertFalse(occupied & indices)
            occupied |= indices
        self.assertEqual(occupied, set(range(layout.tile_count)))

    def test_no_learned_language_sector_or_parameters_anywhere(self) -> None:
        """The v3 learned-language head must not exist in the organism layout or config."""
        self.assertNotIn("L", ORGANISM_SECTOR_ORDER)
        layout = CassiOrganismLayout.build(self.config)
        self.assertEqual(tuple(entry.name for entry in layout.ranges), ORGANISM_SECTOR_ORDER)
        self.assertNotIn("L", [entry.name for entry in layout.ranges])
        self.assertFalse(hasattr(self.config, "language"))
        config_dict = self.config.to_dict()
        self.assertNotIn("language", config_dict)
        for forbidden in ("E", "Wf", "bh", "bo", "resonance_gain"):
            self.assertNotIn(forbidden, config_dict)
        # Serialized checkpoint config must also carry no learned language block.
        encoded = dump_organism_state_bytes(self.state, self.config)
        payload = __import__("torch").load(io.BytesIO(encoded), map_location="cpu", weights_only=True)
        self.assertNotIn("language_config_fingerprint", payload)
        self.assertNotIn("language_layout_fingerprint", payload)
        self.assertNotIn("language", payload["config"])
        for forbidden in ("E", "Wf", "bh", "bo", "resonance_gain"):
            self.assertNotIn(forbidden, payload["config"])
        # The learned-language symbols must not be importable from the module.
        import cassi_organism as organism_module
        for symbol in (
            "LANGUAGE_PARAMETER_NAMES",
            "CassiLanguageConfig",
            "CassiLanguageLayout",
            "CassiLanguageRange",
            "_language_view",
            "_initial_language_values",
            "promote_language_state",
        ):
            self.assertFalse(hasattr(organism_module, symbol), symbol)

    def test_qi_embedding_is_exact_and_q_is_derived(self) -> None:
        restored = qi_state_from_organism(self.state, self.config)
        self.assertTrue(torch.equal(restored.field, self.qi.field))
        self.assertEqual(tuple(QI_COMPONENT_ORDER), ("Y_re", "Y_im", "I_re", "I_im", "VY_re", "VY_im", "VI_re", "VI_im", "epsilon2_ema"))
        self.assertTrue(torch.equal(self.state.epsilon2_ema, self.qi.field.reshape(3, 9, 16, 1)[:, 8, :, 0]))
        rho2 = self.state.rho.square()
        expected_q = rho2 / (
            rho2 + self.qi_controller.config.phi ** -2 + self.state.epsilon.square()
        ).clamp_min(torch.finfo(torch.float32).tiny)
        self.assertTrue(torch.equal(self.state.q, expected_q))
        self.assertNotIn("q", ORGANISM_SECTOR_ORDER)

    def test_world_codec_round_trips_field_stochastic_and_step(self) -> None:
        restored = world_state_from_organism(self.state, self.config)
        self.assertTrue(torch.equal(restored.field, self.world.field))
        self.assertTrue(torch.equal(restored.stochastic, self.world.stochastic))
        self.assertTrue(torch.equal(restored.step, self.world.step))

    def test_successor_and_public_snapshots_cannot_mutate_prior_state(self) -> None:
        before = self.state.arena
        arena_snapshot = self.state.arena
        arena_snapshot.zero_()
        sector_snapshot = self.state.sector(self.config, "m")
        sector_snapshot.zero_()
        self.assertTrue(torch.equal(self.state.arena, before))

        changed_b = torch.linspace(0.1, 0.3, self.config.scale_count)
        changed_z = torch.clamp(
            changed_b * self.state.a / self.config.law.reserve_capacity,
            min=0.0,
            max=1.0,
        )
        changed_p = self.state.p
        changed_p[
            :, self.config.action_width + ACTION_VIABILITY_OFFSET
        ].fill_(float(changed_z.mean().item()))
        successor = successor_organism_state(
            self.state,
            self.config,
            sectors={"b": changed_b, "z": changed_z, "p": changed_p},
        )
        self.assertTrue(torch.equal(self.state.arena, before))
        self.assertTrue(torch.equal(successor.b, changed_b))
        for name in ORGANISM_SECTOR_ORDER:
            if name not in {"b", "z", "p"}:
                self.assertTrue(
                    torch.equal(
                        successor.sector(self.config, name),
                        self.state.sector(self.config, name),
                    )
                )

        constructor_source = self.state.arena
        owned = CassiOrganismState(
            constructor_source,
            self.state.config_fingerprint,
            self.state.layout,
            self.state.metadata,
        )
        constructor_source.fill_(7.0)
        self.assertTrue(torch.equal(owned.arena, before))


    def test_checkpoint_round_trip_identity_and_atomic_file_save(self) -> None:
        encoded = dump_organism_state_bytes(self.state, self.config)
        payload = torch.load(io.BytesIO(encoded), map_location="cpu", weights_only=True)
        self.assertEqual(payload["schema"], ORGANISM_CHECKPOINT_SCHEMA)
        restored = load_organism_state_bytes(encoded, self.config)
        self.assertTrue(torch.equal(restored.arena, self.state.arena))
        self.assertEqual(restored.metadata, self.metadata)
        self.assertEqual(organism_state_sha256(restored, self.config), organism_state_sha256(self.state, self.config))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "organism.pt"
            digest = save_organism_state(path, self.state, self.config)
            self.assertEqual(digest, __import__("hashlib").sha256(path.read_bytes()).hexdigest())
            self.assertTrue(torch.equal(load_organism_state(path, self.config).arena, self.state.arena))
            self.assertFalse(any(candidate.suffix == ".tmp" for candidate in path.parent.iterdir()))

    def test_semantic_tamper_wrong_config_and_legacy_split_artifact_are_rejected(self) -> None:
        encoded = dump_organism_state_bytes(self.state, self.config)
        payload = torch.load(io.BytesIO(encoded), map_location="cpu", weights_only=True)
        payload["arena"] = payload["arena"].clone()
        payload["arena"][0, 0, 0, 0] += 0.25
        stream = io.BytesIO()
        torch.save(payload, stream)
        with self.assertRaisesRegex(CassiOrganismError, "state hash mismatch"):
            load_organism_state_bytes(stream.getvalue(), self.config)
        payload["arena"] = self.state.arena.to(torch.float64)
        payload["state_sha256"] = organism_state_sha256(self.state, self.config)
        stream = io.BytesIO()
        torch.save(payload, stream)
        with self.assertRaisesRegex(CassiOrganismError, "torch.float32"):
            load_organism_state_bytes(stream.getvalue(), self.config)


        wrong = CassiOrganismConfig.from_components(
            QiFieldConfig(scale_count=2, mode_count=16),
            self.world_model.config,
            action_horizon=8,
            shadow_branches=2,
            shadow_steps=3,
            history_capacity=5,
            action_population_capacity=3,
            attention_slots=17,
            theta_width=19,
            teacher_layer_count=4,
        )
        with self.assertRaisesRegex(CassiOrganismError, "configuration mismatch"):
            load_organism_state_bytes(encoded, wrong)
        legacy_v2 = torch.load(io.BytesIO(encoded), map_location="cpu", weights_only=True)
        legacy_v2["schema"] = "cassi.organism.checkpoint.v2"
        stream = io.BytesIO()
        torch.save(legacy_v2, stream)
        with self.assertRaisesRegex(CassiOrganismError, "schema mismatch"):
            load_organism_state_bytes(stream.getvalue(), self.config)

        legacy_stream = io.BytesIO()
        torch.save({"schema": QI_FIELD_STATE_SCHEMA, "field": self.qi.field}, legacy_stream)
        with self.assertRaisesRegex(CassiOrganismError, "legacy split-state artifact"):
            load_organism_state_bytes(legacy_stream.getvalue(), self.config)

    def test_invalid_metadata_nonfinite_arena_and_oversized_layout_fail_closed(self) -> None:
        with self.assertRaisesRegex(CassiOrganismError, "canonical JSON"):
            create_organism_state(self.config, self.qi, self.world, metadata=b'{"z":1, "a":2}')
        invalid_arena = self.state.arena
        invalid_arena[0, 0, 0, 0] = float("nan")
        bad = CassiOrganismState(
            invalid_arena,
            self.state.config_fingerprint,
            self.state.layout,
            self.state.metadata,
        )
        with self.assertRaisesRegex(CassiOrganismError, "non-finite"):
            bad.validate(self.config)
        with self.assertRaises(CassiOrganismError):
            CassiOrganismConfig.from_components(
                self.qi_controller.config,
                self.world_model.config,
                attention_slots=1 << 20,
                action_population_capacity=1 << 20,
            )

    def test_configuration_and_persistent_numeric_bounds_fail_closed(self) -> None:
        with self.assertRaisesRegex(CassiOrganismError, "attention_slots"):
            CassiOrganismConfig.from_components(
                self.qi_controller.config,
                self.world_model.config,
                attention_slots=6,
            )
        with self.assertRaisesRegex(CassiOrganismError, "reserve_capacity"):
            CassiOrganismLawConfig(reserve_capacity=1.0e39)
        with self.assertRaisesRegex(CassiOrganismError, "history rows"):
            successor_organism_state(
                self.state,
                self.config,
                sectors={"h": torch.full_like(self.state.h, 1.01)},
            )


if __name__ == "__main__":
    unittest.main()
