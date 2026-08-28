import dataclasses
import hashlib
import unittest

import torch

from cassi_conscious_field import (
    AccessLevel,
    CassiConsciousField,
    CassiConsciousFieldError,
    ConsciousFieldConfig,
    MetacognitiveState,
    ProvenancePolicy,
    tensor_wave_sha256,
)
from cassi_conscious_protocol import (
    ActorClass,
    CassiConsciousProtocolError,
    CassiExperienceEvent,
    EventKind,
    RealityStatus,
    create_event,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState


class CassiConsciousFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        config = QiFieldConfig(
            scale_count=3,
            mode_count=16,
            alphabet_size=260,
            read_threshold=1e-9,
            emission_floor=1e-9,
        )
        conscious_config = ConsciousFieldConfig(
            access_threshold=0.0,
            minimum_cross_scale_coherence=0.1,
            maximum_access_uncertainty=1.0,
        )
        self.controller = QiFieldController(config)
        self.field = CassiConsciousField(self.controller, conscious_config)
        self.initial_state = self.field.initial_state(dtype=torch.float64)

    def make_event(
        self,
        kind: EventKind,
        reality_status: RealityStatus,
        actor: ActorClass,
        payload: bytes,
        **kwargs: object,
    ) -> CassiExperienceEvent:
        return create_event(
            sequence=1,
            kind=kind,
            reality_status=reality_status,
            actor=actor,
            payload=payload,
            source_id="test",
            **kwargs,
        )

    def bind_event_to_wave(
        self,
        event: CassiExperienceEvent,
        wave: torch.Tensor,
    ) -> CassiExperienceEvent:
        return create_event(
            sequence=event.sequence,
            kind=event.kind,
            reality_status=event.reality_status,
            actor=event.actor,
            payload=event.payload,
            source_id=event.source_id,
            parent_event_id=event.parent_event_id,
            branch_id=event.branch_id,
            boundary_wave_sha256=tensor_wave_sha256(wave),
        )

    def observed_perception(
        self,
        payload: bytes = b"actual",
        **kwargs: object,
    ) -> CassiExperienceEvent:
        return self.make_event(
            EventKind.PERCEPTION,
            RealityStatus.OBSERVED_REALITY,
            ActorClass.ENVIRONMENT,
            payload,
            **kwargs,
        )

    def imagined_hypothesis(
        self,
        payload: bytes = b"guess",
        **kwargs: object,
    ) -> CassiExperienceEvent:
        return self.make_event(
            EventKind.IMAGINATION,
            RealityStatus.HYPOTHESIS,
            ActorClass.LOCAL_AGENT,
            payload,
            **kwargs,
        )

    def local_deliberation(
        self,
        payload: bytes = b"internal branch selection",
        **kwargs: object,
    ) -> CassiExperienceEvent:
        return self.make_event(
            EventKind.DELIBERATION,
            RealityStatus.DERIVED_DELIBERATION,
            ActorClass.LOCAL_AGENT,
            payload,
            branch_id="d" * 64,
            **kwargs,
        )

    def local_action_intent(
        self,
        payload: bytes = b"act",
        **kwargs: object,
    ) -> CassiExperienceEvent:
        return self.make_event(
            EventKind.ACTION_INTENT,
            RealityStatus.AGENT_INTENT,
            ActorClass.LOCAL_AGENT,
            payload,
            **kwargs,
        )

    def public_accessible_state(self) -> QiFieldState:
        state = self.field.initial_state(dtype=torch.float64)
        packed_state = state.field.reshape(3, 9, 16, 1)
        denominator = 1 + self.controller.config.phi**2

        for scale in range(3):
            codebook_wave = self.controller.codebook(scale, dtype=torch.float64)[3]
            packed_state[scale, 0, :8, 0] = codebook_wave[:, 0] / denominator
            packed_state[scale, 1, :8, 0] = codebook_wave[:, 1] / denominator
            packed_state[scale, 2, :8, 0] = (
                -self.controller.config.phi * codebook_wave[:, 0] / denominator
            )
            packed_state[scale, 3, :8, 0] = (
                -self.controller.config.phi * codebook_wave[:, 1] / denominator
            )

        self.assertTrue(self.field.access_gate(state).granted)
        return state

    def test_single_lane_and_protocol_legality(self) -> None:
        with self.assertRaises(CassiConsciousFieldError):
            self.field.initial_state(2)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.structural_self(self.controller.initial_state(2))
        with self.assertRaises(CassiConsciousProtocolError):
            self.make_event(EventKind.COMMITMENT, RealityStatus.HYPOTHESIS, ActorClass.LOCAL_AGENT, b'x')
        self.assertEqual(self.make_event(EventKind.COMMITMENT, RealityStatus.AGENT_INTENT, ActorClass.LOCAL_AGENT, b'x'), self.make_event(EventKind.COMMITMENT, RealityStatus.AGENT_INTENT, ActorClass.LOCAL_AGENT, b'x'))

    def test_chunked_complex_boundary_and_explicit_validator(self) -> None:
        a = self.field.boundary.encode(self.observed_perception(bytes(range(256)) * 4), self.initial_state)
        b = self.field.boundary.encode(self.observed_perception(bytes(reversed(range(256))) * 4), self.initial_state)
        self.assertTrue(torch.isfinite(a).all())
        self.assertFalse(torch.equal(a, b))
        self.assertLessEqual(float(torch.linalg.vector_norm(a, dim=-1).amax()), 1.000001)
        bad = torch.zeros((1, 8, 2), dtype=torch.float32)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, self.imagined_hypothesis(), proposal_wave=bad)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, self.local_action_intent(), proposal_wave=torch.zeros((1, 8, 2), dtype=torch.float64))

    def test_self_access_interoception_metacognition_and_recall(self) -> None:
        one = self.initial_state.clone()
        one.field.reshape(3, 9, 16, 1)[0, 0, :8, 0] = 1
        self.assertIn(self.field.access_gate(one).level, {AccessLevel.ABSTAIN, AccessLevel.LOCAL_ONLY})
        s = self.public_accessible_state()
        x = self.field.structural_self(s)
        self.assertTrue(all(torch.isfinite(torch.tensor(dataclasses.astuple(x)[:-1]))))
        v = self.field.interoception(s, prior_state=s, contradiction_energy=0.25)
        self.assertEqual(len(v.vector), 7)
        self.assertTrue(all((0 <= z <= 1 for z in v.vector)))
        m = self.field.metacognition(s, residual_energy=0.2)
        self.assertEqual(m.residual_energy, 0.2)
        q = self.make_event(EventKind.RECALL, RealityStatus.DERIVED_RECALL, ActorClass.LOCAL_AGENT, b'query')
        r = self.field.recall(s, q)
        self.assertIsInstance(r.available, bool)
        self.assertEqual(r.access.level, self.field.access_gate(self.controller.evolve(self.controller.sense_wave(s.clone(), self.field.boundary.encode(q, s), structured_source=0.35))).level)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.metacognition(s, residual_energy=float('nan'))

    def test_commit_recall_requires_selected_derived_recall_and_exact_wave(self) -> None:
        root = self.public_accessible_state()
        root_snapshot = root.field.clone()
        raw = self.make_event(
            EventKind.RECALL,
            RealityStatus.DERIVED_RECALL,
            ActorClass.LOCAL_AGENT,
            b"selected recall",
        )
        wave = self.field.boundary.encode(raw, root)
        selected = self.bind_event_to_wave(raw, wave)
        readout = self.field.recall(root, raw)
        self.assertTrue(torch.equal(root.field, root_snapshot))
        transition = self.field.commit_recall(root, selected, wave)
        self.assertIs(transition.event, selected)
        self.assertTrue(torch.equal(transition.input_wave, wave))
        self.assertEqual(tensor_wave_sha256(transition.input_wave), selected.boundary_wave_sha256)
        self.assertEqual(transition.applied_correction_gain, 0.0)
        self.assertTrue(torch.isfinite(transition.state.field).all())
        self.assertIsInstance(readout.available, bool)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_recall(root, raw, wave)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_recall(root, self.observed_perception())

    def test_explicit_observation_wave_requires_exact_digest(self) -> None:
        raw_event = self.observed_perception()
        wave = self.field.boundary.encode(raw_event, self.initial_state)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.perceive(self.initial_state, raw_event, observation_wave=wave)
        mismatched = self.observed_perception(boundary_wave_sha256='0' * 64)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.perceive(self.initial_state, mismatched, observation_wave=wave)
        exact = self.bind_event_to_wave(raw_event, wave)
        transition = self.field.perceive(self.initial_state, exact, observation_wave=wave)
        self.assertEqual(tensor_wave_sha256(transition.input_wave), exact.boundary_wave_sha256)
        self.assertTrue(torch.equal(transition.input_wave, wave))
        self.assertNotEqual(transition.input_wave.data_ptr(), wave.data_ptr())
        wave.add_(0.1)
        self.assertFalse(torch.equal(transition.input_wave, wave))
        self.assertTrue(torch.isfinite(transition.state.field).all())

    def test_explicit_proposal_wave_requires_exact_digest(self) -> None:
        raw_event = self.imagined_hypothesis()
        wave = self.field.boundary.encode(raw_event, self.initial_state)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, raw_event, proposal_wave=wave)
        mismatched = self.imagined_hypothesis(boundary_wave_sha256='f' * 64)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, mismatched, proposal_wave=wave)
        exact = self.bind_event_to_wave(raw_event, wave)
        branch = self.field.begin_imagination(self.initial_state, exact, proposal_wave=wave)
        self.assertEqual(branch.receipt.proposal_wave_sha256, tensor_wave_sha256(wave))


    def test_canonical_empty_digest_uses_byte_encoder_only(self) -> None:
        event = self.observed_perception(b'canonical')
        self.assertEqual(event.boundary_wave_sha256, '')
        expected_wave = self.field.boundary.encode(event, self.initial_state)
        transition = self.field.perceive(self.initial_state, event)
        self.assertTrue(torch.equal(transition.input_wave, expected_wave))
        self.assertTrue(torch.isfinite(transition.state.field).all())

    def test_explicit_report_wave_requires_exact_digest(self) -> None:
        raw_event = self.make_event(EventKind.EXTERNAL_REPORT, RealityStatus.REPORTED_EVIDENCE, ActorClass.EXTERNAL_AGENT, b'report')
        wave = self.field.boundary.encode(raw_event, self.initial_state)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.receive_report(self.initial_state, raw_event, report_wave=wave)
        mismatched = self.make_event(EventKind.EXTERNAL_REPORT, RealityStatus.REPORTED_EVIDENCE, ActorClass.EXTERNAL_AGENT, b'report', boundary_wave_sha256='1' * 64)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.receive_report(self.initial_state, mismatched, report_wave=wave)
        exact = self.bind_event_to_wave(raw_event, wave)
        transition = self.field.receive_report(self.initial_state, exact, report_wave=wave)
        self.assertTrue(torch.equal(transition.input_wave, wave))
        self.assertEqual(tensor_wave_sha256(transition.input_wave), exact.boundary_wave_sha256)
        self.assertTrue(torch.isfinite(transition.state.field).all())

    def test_commit_deliberation_is_noncorrective_and_isolated(self) -> None:
        root = self.public_accessible_state()
        root_snapshot = root.field.clone()
        deliberation = self.local_deliberation()

        transition = self.field.commit_deliberation(root, deliberation)

        self.assertIs(transition.event, deliberation)
        self.assertEqual(transition.correction_energy, 0.0)
        self.assertEqual(transition.applied_correction_gain, 0.0)
        self.assertTrue(torch.equal(root.field, root_snapshot))
        self.assertTrue(
            torch.equal(
                transition.input_wave,
                self.field.boundary.encode(deliberation, root),
            )
        )
        self.assertLessEqual(
            self.field.config.provenance.trust_for(deliberation),
            self.field.config.provenance.recall_trust,
        )

        with self.assertRaises(CassiConsciousFieldError):
            self.field.perceive(root, deliberation)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.receive_report(root, deliberation)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_action_intent(root, deliberation)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_commitment(root, deliberation)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_recall(root, deliberation)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(root, deliberation)
        branch = self.field.begin_imagination(root, self.imagined_hypothesis())
        with self.assertRaises(CassiConsciousFieldError):
            self.field.reconcile_branch(root, branch, deliberation)

    def test_commit_deliberation_rejects_missing_branch_and_explicit_wave(self) -> None:
        without_branch = self.make_event(
            EventKind.DELIBERATION,
            RealityStatus.DERIVED_DELIBERATION,
            ActorClass.LOCAL_AGENT,
            b"internal branch selection",
        )
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_deliberation(self.initial_state, without_branch)

        explicit_wave = self.local_deliberation(boundary_wave_sha256="0" * 64)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.commit_deliberation(self.initial_state, explicit_wave)

    def test_corrective_wave_and_commitment_noncorrective(self) -> None:
        raw_observation = self.observed_perception()
        w = self.field.boundary.encode(raw_observation, self.initial_state)
        observation = self.bind_event_to_wave(raw_observation, w)
        t = self.field.perceive(self.initial_state, observation, observation_wave=w)
        self.assertGreaterEqual(t.correction_energy, 0)
        commit = self.make_event(EventKind.COMMITMENT, RealityStatus.AGENT_INTENT, ActorClass.LOCAL_AGENT, b'persist')
        ct = self.field.commit_commitment(self.initial_state, commit)
        self.assertEqual(ct.correction_energy, 0.0)
        self.assertTrue(
            torch.equal(
                ct.input_wave,
                self.field.boundary.encode(commit, self.initial_state),
            )
        )
        before = self.initial_state.field.reshape(3, 9, 16, 1)
        after = ct.state.field.reshape(3, 9, 16, 1)
        self.assertLessEqual(float(torch.linalg.vector_norm(after[-1] - before[-1])), float(torch.linalg.vector_norm(after[0] - before[0])))

    def test_reported_evidence_has_lower_observable_selective_gain(self) -> None:
        direct = self.observed_perception(b'matched')
        report = self.make_event(EventKind.EXTERNAL_REPORT, RealityStatus.REPORTED_EVIDENCE, ActorClass.EXTERNAL_AGENT, b'matched')
        direct_transition = self.field.perceive(self.initial_state, direct)
        report_transition = self.field.receive_report(self.initial_state, report)
        self.assertLess(report_transition.applied_correction_gain, direct_transition.applied_correction_gain)
        self.assertLessEqual(direct_transition.applied_correction_gain, self.field.config.maximum_correction_gain)
        self.assertLessEqual(report_transition.applied_correction_gain, self.field.config.maximum_correction_gain)

    def test_branch_integrity_root_isolation_and_actual_wave_reconciliation(self) -> None:
        root = self.initial_state
        root_bytes = root.field.clone()
        raw_proposal = self.imagined_hypothesis()
        proposal_wave = torch.full((1, 8, 2), 0.1, dtype=torch.float64)
        proposal = self.bind_event_to_wave(raw_proposal, proposal_wave)
        b = self.field.begin_imagination(root, proposal, proposal_wave=proposal_wave, steps=2)
        self.assertTrue(torch.equal(root.field, root_bytes))
        self.assertEqual(b.receipt.proposal_wave_sha256, hashlib.sha256(proposal_wave.numpy().tobytes()).hexdigest())
        raw_actual = self.observed_perception(b'different')
        actual_wave = self.field.boundary.encode(raw_actual, root)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.reconcile_branch(root, b, raw_actual, actual_wave=actual_wave)
        mismatched_actual = self.bind_event_to_wave(raw_actual, torch.zeros_like(actual_wave))
        with self.assertRaises(CassiConsciousFieldError):
            self.field.reconcile_branch(root, b, mismatched_actual, actual_wave=actual_wave)
        actual = self.bind_event_to_wave(raw_actual, actual_wave)
        rec = self.field.reconcile_branch(root, b, actual, actual_wave=actual_wave)
        self.assertFalse(rec.contradiction.matched)
        self.assertGreater(rec.semantic_trace_energy, 0)
        self.assertEqual(rec.contradiction.proposal_wave_sha256, b.receipt.proposal_wave_sha256)
        self.assertEqual(
            rec.contradiction.predicted_wave_sha256,
            tensor_wave_sha256(b.predicted_wave),
        )
        self.assertEqual(
            rec.contradiction.residual_sha256,
            tensor_wave_sha256(actual_wave - b.predicted_wave),
        )
        expected_contradiction = create_event(
            sequence=actual.sequence + 1,
            kind=EventKind.CONTRADICTION,
            reality_status=RealityStatus.CONTRADICTION_FACT,
            actor=ActorClass.LOCAL_AGENT,
            payload=bytes.fromhex(tensor_wave_sha256(b.predicted_wave))
            + bytes.fromhex(tensor_wave_sha256(actual_wave)),
            source_id="cassi-conscious-field",
            parent_event_id=actual.event_id,
            branch_id=b.branch_id,
        )
        self.assertEqual(rec.contradiction_event, expected_contradiction)

        matching_actual = self.bind_event_to_wave(
            self.observed_perception(b"matching"),
            b.predicted_wave,
        )
        matched = self.field.reconcile_branch(
            root,
            b,
            matching_actual,
            actual_wave=b.predicted_wave,
        )
        self.assertTrue(matched.contradiction.matched)
        self.assertIsNone(matched.contradiction_event)
        for changed in (dataclasses.replace(b, proposal_wave=b.proposal_wave + 0.01), dataclasses.replace(b, predicted_wave=b.predicted_wave + 0.01), dataclasses.replace(b, state=QiFieldState(b.state.field + 0.01)), dataclasses.replace(b, receipt=dataclasses.replace(b.receipt, imagination_steps=3))):
            with self.assertRaises(CassiConsciousFieldError):
                self.field.reconcile_branch(root, changed, actual, actual_wave=actual_wave)

    def test_branch_identity_binds_steps_and_explicit_wave(self) -> None:
        raw_event = self.imagined_hypothesis(b'branch')
        wave = torch.full((1, 8, 2), 0.1, dtype=torch.float64)
        event = self.bind_event_to_wave(raw_event, wave)
        one_step = self.field.begin_imagination(self.initial_state, event, proposal_wave=wave, steps=1)
        two_steps = self.field.begin_imagination(self.initial_state, event, proposal_wave=wave, steps=2)
        altered_wave = wave.clone()
        altered_wave[0, 0, 0] += 0.01
        altered_event = self.bind_event_to_wave(raw_event, altered_wave)
        altered = self.field.begin_imagination(self.initial_state, altered_event, proposal_wave=altered_wave, steps=1)
        self.assertNotEqual(one_step.branch_id, two_steps.branch_id)
        self.assertNotEqual(one_step.branch_id, altered.branch_id)
        self.assertEqual(one_step.receipt.branch_id, one_step.branch_id)

    def test_deliberation_order_independence_and_world_linked_agency(self) -> None:
        state = self.public_accessible_state()
        first = self.field.propose_action(state, [b"b", b"a"], sequence=4)
        second = self.field.propose_action(state, [b"a", b"b"], sequence=4)
        self.assertTrue(first.inert)
        self.assertEqual(first.intent.payload, second.intent.payload)
        self.assertEqual(first.score, second.score)
        self.assertEqual(
            first.branch.root_field_sha256,
            hashlib.sha256(state.field.contiguous().numpy().tobytes()).hexdigest(),
        )
        hypothesis = self.imagined_hypothesis(
            b"learned consequence",
            parent_event_id=first.intent.event_id,
        )
        branch = self.field.begin_imagination(
            state,
            hypothesis,
            root_event_id=first.intent.event_id,
        )
        self.assertIs(branch.proposal_event.reality_status, RealityStatus.HYPOTHESIS)
        self.assertEqual(branch.root_event_id, first.intent.event_id)
        raw_outcome = create_event(
            sequence=5,
            kind=EventKind.ACTION_OUTCOME,
            reality_status=RealityStatus.OBSERVED_REALITY,
            actor=ActorClass.ENVIRONMENT,
            payload=b"out",
            source_id="test",
            parent_event_id=first.intent.event_id,
        )
        outcome = self.bind_event_to_wave(raw_outcome, branch.predicted_wave)
        agency = self.field.agency_attribution(
            first.intent,
            outcome,
            branch,
            state,
            outcome_wave=branch.predicted_wave,
        )
        self.assertTrue(agency.supported)
        self.assertGreater(agency.evidence, 0)
        forged_intent = self.local_action_intent(b"forged")
        forged_outcome = create_event(
            sequence=5,
            kind=EventKind.ACTION_OUTCOME,
            reality_status=RealityStatus.OBSERVED_REALITY,
            actor=ActorClass.ENVIRONMENT,
            payload=b"out",
            source_id="test",
            parent_event_id=forged_intent.event_id,
        )
        forged_outcome = self.bind_event_to_wave(
            forged_outcome,
            branch.predicted_wave,
        )
        forged = self.field.agency_attribution(
            forged_intent,
            forged_outcome,
            branch,
            state,
            outcome_wave=branch.predicted_wave,
        )
        self.assertFalse(forged.supported)
        self.assertEqual(forged.reason, "insufficient linked access")
        with self.assertRaises(CassiConsciousFieldError):
            self.field.agency_attribution(
                first.intent,
                outcome,
                dataclasses.replace(
                    branch,
                    proposal_wave=branch.proposal_wave + 0.1,
                ),
                state,
                outcome_wave=branch.predicted_wave,
            )

    def test_explicit_outcome_wave_requires_exact_digest_for_agency(self) -> None:
        state = self.public_accessible_state()
        intent = self.local_action_intent(b"agency")
        hypothesis = self.imagined_hypothesis(
            b"learned consequence",
            parent_event_id=intent.event_id,
        )
        branch = self.field.begin_imagination(
            state,
            hypothesis,
            root_event_id=intent.event_id,
        )
        raw_outcome = create_event(
            sequence=5,
            kind=EventKind.ACTION_OUTCOME,
            reality_status=RealityStatus.OBSERVED_REALITY,
            actor=ActorClass.ENVIRONMENT,
            payload=b"outcome",
            source_id="test",
            parent_event_id=intent.event_id,
        )
        outcome_wave = branch.predicted_wave
        with self.assertRaises(CassiConsciousFieldError):
            self.field.agency_attribution(
                intent,
                raw_outcome,
                branch,
                state,
                outcome_wave=outcome_wave,
            )
        mismatched = create_event(
            sequence=raw_outcome.sequence,
            kind=raw_outcome.kind,
            reality_status=raw_outcome.reality_status,
            actor=raw_outcome.actor,
            payload=raw_outcome.payload,
            source_id=raw_outcome.source_id,
            parent_event_id=raw_outcome.parent_event_id,
            boundary_wave_sha256="2" * 64,
        )
        with self.assertRaises(CassiConsciousFieldError):
            self.field.agency_attribution(
                intent,
                mismatched,
                branch,
                state,
                outcome_wave=outcome_wave,
            )
        exact = self.bind_event_to_wave(raw_outcome, outcome_wave)
        agency = self.field.agency_attribution(
            intent,
            exact,
            branch,
            state,
            outcome_wave=outcome_wave,
        )
        self.assertTrue(agency.supported)

    def test_public_transitions_reach_accessible_without_tensor_mutation(self) -> None:
        """Repeated direct observations plus normal consolidation reach access."""
        state = self.field.initial_state(dtype=torch.float64)
        event = self.observed_perception(b'coherent repeated experience')
        for _ in range(64):
            state = self.field.perceive(state, event).state
        access = self.field.access_gate(state)
        self.assertEqual(access.level, AccessLevel.ACCESSIBLE)
        self.assertTrue(access.granted)
        self.assertGreaterEqual(access.participating_scales, 2)

    def test_prediction_receipt_scalar_tampering_fails_closed(self) -> None:
        branch = self.field.begin_imagination(self.initial_state, self.imagined_hypothesis())
        actual = self.observed_perception(b'actual')
        for receipt in (dataclasses.replace(branch.receipt, predicted_symbol=17), dataclasses.replace(branch.receipt, access_granted=not branch.receipt.access_granted), dataclasses.replace(branch.receipt, imagination_steps=branch.receipt.imagination_steps + 1)):
            tampered = dataclasses.replace(branch, receipt=receipt)
            with self.assertRaises(CassiConsciousFieldError):
                self.field.reconcile_branch(self.initial_state, tampered, actual)

    def test_invalid_recall_and_eligibility_events_are_rejected(self) -> None:
        perception = self.observed_perception()
        with self.assertRaises(CassiConsciousFieldError):
            self.field.recall(self.initial_state, perception)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.eligibility(self.initial_state, self.imagined_hypothesis())

    def test_imagination_root_and_steps_domain_validation(self) -> None:
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, self.imagined_hypothesis(), root_event_id=True)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, self.imagined_hypothesis(), root_event_id='not-a-digest')
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, self.imagined_hypothesis(), steps=True)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(self.initial_state, self.imagined_hypothesis(), steps=0)

    def test_public_candidate_and_branch_step_bounds_reject_before_work(self) -> None:
        defaults = ConsciousFieldConfig()
        self.assertEqual(defaults.maximum_action_candidates, 32)
        self.assertEqual(defaults.maximum_imagination_steps, 64)
        with self.assertRaises(CassiConsciousFieldError):
            ConsciousFieldConfig(maximum_action_candidates=33)
        with self.assertRaises(CassiConsciousFieldError):
            ConsciousFieldConfig(maximum_imagination_steps=65)

        candidates = tuple(b"candidate" for _ in range(33))
        with self.assertRaises(CassiConsciousFieldError):
            self.field.propose_commitment(object(), candidates, sequence=1)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.propose_action(object(), candidates, sequence=1)
        with self.assertRaises(CassiConsciousFieldError):
            self.field.begin_imagination(object(), object(), steps=65)

    def test_direct_observation_favors_fast_over_deepest_scale(self) -> None:
        before = self.initial_state.field.reshape(3, 9, 16, 1).clone()
        after = self.field.perceive(self.initial_state, self.observed_perception(b'material evidence')).state.field.reshape(3, 9, 16, 1)
        fast_delta = float(torch.linalg.vector_norm(after[0] - before[0]))
        deepest_delta = float(torch.linalg.vector_norm(after[-1] - before[-1]))
        self.assertGreater(fast_delta, deepest_delta)
        self.assertLessEqual(deepest_delta / fast_delta, 0.25)

    def test_constructor_and_configuration_validation(self) -> None:
        with self.assertRaises(CassiConsciousFieldError):
            CassiConsciousField(object(), ConsciousFieldConfig())
        with self.assertRaises(CassiConsciousFieldError):
            CassiConsciousField(self.controller, object())
        with self.assertRaises(CassiConsciousFieldError):
            CassiConsciousField(self.controller, ConsciousFieldConfig(minimum_access_scales=4))
        for invalid_value in (float('nan'), float('inf'), -0.1, 1.1):
            with self.assertRaises(CassiConsciousFieldError):
                ProvenancePolicy(observed_trust=invalid_value)

    def test_protocol_rejects_malformed_parent_and_branch_digests(self) -> None:
        with self.assertRaises(CassiConsciousProtocolError):
            self.observed_perception(parent_event_id='not-a-sha256-digest')
        with self.assertRaises(CassiConsciousProtocolError):
            self.observed_perception(branch_id='also-not-a-sha256-digest')

    def test_eligibility_rejects_each_wrong_legal_event_shape(self) -> None:
        wrong_kind = self.make_event(EventKind.ACTION_OUTCOME, RealityStatus.OBSERVED_REALITY, ActorClass.LOCAL_AGENT, b'outcome')
        wrong_status = self.make_event(EventKind.IMAGINATION, RealityStatus.HYPOTHESIS, ActorClass.LOCAL_AGENT, b'hypothesis')
        wrong_actor = self.make_event(EventKind.TEACHER_PROPOSAL, RealityStatus.EXTERNAL_PROPOSAL, ActorClass.TEACHER, b'teacher')
        for event in (wrong_kind, wrong_status, wrong_actor):
            with self.assertRaises(CassiConsciousFieldError):
                self.field.eligibility(self.initial_state, event)

    def test_metacognition_states_and_residual_validation(self) -> None:
        initial = self.field.metacognition(self.initial_state)
        self.assertIn(initial.state, (MetacognitiveState.ABSTAIN, MetacognitiveState.LOCAL_ONLY))
        accessible_state = self.field.initial_state(dtype=torch.float64)
        repeated_event = self.observed_perception(b'coherent repeated experience')
        for _ in range(64):
            accessible_state = self.field.perceive(accessible_state, repeated_event).state
        accessible = self.field.metacognition(accessible_state)
        contradicted = self.field.metacognition(accessible_state, residual_energy=0.1)
        self.assertEqual(accessible.state, MetacognitiveState.ACCESSIBLE)
        self.assertEqual(contradicted.state, MetacognitiveState.CONTRADICTED)
        for invalid_residual in (float('nan'), float('inf'), -0.1):
            with self.assertRaises(CassiConsciousFieldError):
                self.field.metacognition(accessible_state, residual_energy=invalid_residual)

    def test_action_proposal_abstains_when_initial_state_is_inaccessible(self) -> None:
        proposal = self.field.propose_action(self.initial_state, (b'first', b'known winner'), sequence=2)
        self.assertIsNone(proposal)

    def test_action_selection_is_order_independent_and_nonfirst(self) -> None:
        accessible_state = self.public_accessible_state()
        forward = self.field.propose_action(accessible_state, (b'first', b'known winner'), sequence=3)
        reversed_order = self.field.propose_action(accessible_state, (b'known winner', b'first'), sequence=3)
        self.assertIsNotNone(forward)
        self.assertIsNotNone(reversed_order)
        self.assertEqual(forward.intent.payload, b'known winner')
        self.assertNotEqual(forward.candidate_index, 0)
        self.assertEqual(reversed_order.intent.payload, b'known winner')
        self.assertEqual(forward.score, reversed_order.score)
    def test_structural_self_separates_fast_and_slow_scale_differentials(self) -> None:
        state = self.initial_state.clone()
        packed_state = state.field.reshape(3, 9, 16, 1)
        packed_state[0, 0, 0, 0] = 0.5

        scale_zero_only = self.field.structural_self(state)
        self.assertGreater(scale_zero_only.fast_differential, 0.0)
        self.assertEqual(scale_zero_only.slow_differential, 0.0)

        packed_state[-1, 0, 0, 0] = 0.25
        both_scales = self.field.structural_self(state)
        self.assertNotEqual(both_scales.fast_differential, both_scales.slow_differential)
        self.assertTrue(torch.isfinite(torch.tensor(both_scales.structural_strength)))

    def test_structural_self_clamps_epsilon2_ema_for_finite_bounded_stability(self) -> None:
        state = self.initial_state.clone()
        epsilon = state.field.reshape(3, 9, 16, 1)[:, 8]
        epsilon.fill_(-1.0)
        zeroed = self.field.structural_self(state)
        self.assertEqual(zeroed.epsilon_stability, 1.0)

        epsilon.fill_(0.5)
        positive = self.field.structural_self(state)
        self.assertAlmostEqual(positive.epsilon_stability, 1.0 / 1.5)
        self.assertGreaterEqual(positive.epsilon_stability, 0.0)
        self.assertLessEqual(positive.epsilon_stability, 1.0)
        self.assertTrue(torch.isfinite(torch.tensor(positive.structural_strength)))

    def test_default_conscious_config_reaches_access_after_bounded_direct_evidence(self) -> None:
        field = CassiConsciousField(self.controller, ConsciousFieldConfig())
        state = field.initial_state(dtype=torch.float64)
        event = self.observed_perception(b"coherent repeated experience")
        for _ in range(128):
            state = field.perceive(state, event).state
            if field.access_gate(state).level is AccessLevel.ACCESSIBLE:
                break
        self.assertEqual(field.access_gate(state).level, AccessLevel.ACCESSIBLE)

    def test_default_config_adapts_to_single_scale_single_lane(self) -> None:
        controller = QiFieldController(
            QiFieldConfig(
                scale_count=1,
                mode_count=16,
                alphabet_size=260,
                read_threshold=1e-9,
                emission_floor=1e-9,
            )
        )
        field = CassiConsciousField(controller)
        self.assertEqual(field.config.minimum_access_scales, 1)
        state = field.initial_state(dtype=torch.float64)
        transition = field.perceive(state, self.observed_perception(b"one scale"))
        self.assertTrue(torch.isfinite(transition.state.field).all())

if __name__ == '__main__':
    unittest.main()
