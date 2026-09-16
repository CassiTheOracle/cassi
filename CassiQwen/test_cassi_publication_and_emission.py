#!/usr/bin/env python3
"""Behavioral coverage for paired publication eligibility and field-owned emission."""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from cassi_field_qwen_workbench import (
    CassiFieldWorkMemory,
    WorkMemoryRecord,
    _encode_memory_block,
    emission_frame,
    emitter_record,
    fit_emission_frame,
    measure_segment_tokens,
    work_prompt,
)
from cassi_model_instrument import (
    CoupledTransactionJournal,
    QwenNativeInstrument,
    differential_field_state,
)

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "native/llama.cpp/b8/bin/Release/cassi-qwen.exe"
MODEL = ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
STATE = ROOT / "_diag/latent-reasoning/zero-state-4scale.f32"
PROMPT = "What color is the workshop marker? Reply with the color only."
FACT_CONTEXT = {"kind": "workshop-fact", "topic": "marker"}
RESULT_CONTEXT = {"kind": "native-model-result", "mode": "field"}
INSTRUMENT_SOURCE = textwrap.dedent(
    """
    QwenNativeInstrument(
        executable=ROOT / "native/llama.cpp/b8/bin/Release/cassi-qwen.exe",
        model=ROOT / "Qwen3.5-0.8B-Q4_0.gguf",
        state=ROOT / "_diag/latent-reasoning/zero-state-4scale.f32",
        backend="cpu",
    )
    """
).strip()


def instrument(*, native_context: bool = True) -> QwenNativeInstrument:
    return QwenNativeInstrument(
        executable=BINARY,
        model=MODEL,
        state=STATE,
        backend="cpu",
        native_context=native_context,
    )


def fact(color: str, *, operation: str) -> WorkMemoryRecord:
    return WorkMemoryRecord(
        source_id="workshop.marker",
        context=FACT_CONTEXT,
        payload={"color": color},
        observed_timestamp=f"logical:{operation}",
        labels=("regression",),
    )


class PublicationEligibilityTests(unittest.TestCase):
    def test_interrupted_publication_is_not_recallable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "owner"
            worker = textwrap.dedent(
                """
                import os, sys
                from pathlib import Path

                ROOT = Path(sys.argv[1]).resolve()
                sys.path.insert(0, str(ROOT))
                from cassi_field_qwen_workbench import CassiFieldWorkMemory
                from cassi_model_instrument import CoupledTransactionJournal, QwenNativeInstrument

                def die(*args, **kwargs):
                    os._exit(91)

                CoupledTransactionJournal.seal = die
                with CassiFieldWorkMemory(Path(sys.argv[2])) as memory:
                    memory.execute_native(
                        operation_id="interrupted-trial",
                        instrument={instrument},
                        mode="field",
                        prompt="Give one word.",
                        tokens=2,
                        sequence=1,
                    )
                """
            ).format(instrument=INSTRUMENT_SOURCE)
            completed = subprocess.run(
                [sys.executable, "-c", worker, str(ROOT), str(home)],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                timeout=900,
            )
            self.assertEqual(completed.returncode, 91, completed.stderr)
            with CassiFieldWorkMemory(home) as memory:
                pending = memory.state_receipt()["unsettled_coupled_transactions"]
                self.assertEqual(pending["count"], 1, pending)
                self.assertEqual(pending["transactions"][0]["status"], "staged", pending)
                result = memory.recall(
                    {"kind": "native-model-result", "mode": "field", "operation": "interrupted-trial"},
                    operation_label="interrupted-trial",
                )
                self.assertEqual(result["status"], "support-gap", result["records"])
                self.assertEqual(result["excluded_ineligible_count"], 1, result)
                excluded = result["excluded_ineligible"][0]
                self.assertEqual(excluded["operation_id"], "interrupted-trial")
                self.assertEqual(excluded["transaction_status"], "staged")
                self.assertEqual(excluded["reason"], "unaccepted-trial")

    def test_committed_publication_is_recallable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "owner"
            with CassiFieldWorkMemory(home) as memory:
                executed = memory.execute_native(
                    operation_id="committed-trial",
                    instrument=instrument(),
                    mode="field",
                    prompt="Give one word.",
                    tokens=2,
                    sequence=1,
                )
                self.assertEqual(executed["status"], "committed")
                self.assertTrue(executed["publication"]["eligible"], executed["publication"])
                self.assertEqual(executed["continuation_class"], "field-only")
                self.assertEqual(executed["measured"]["semantic_transitions"], 1)
                result = memory.recall(
                    {"kind": "native-model-result", "mode": "field", "operation": "committed-trial"},
                    operation_label="committed-trial",
                )
                self.assertEqual(result["status"], "supported")
                self.assertEqual(result["excluded_ineligible_count"], 0)
                self.assertEqual(result["records"][0]["publication_status"], "committed")
                journal = CoupledTransactionJournal(home / "coupled-transactions")
                self.assertEqual(journal.unsettled(), ())
                staged = journal._read("committed-trial")
                self.assertEqual(staged["work"]["native_forward_passes"], 0)
                self.assertEqual(staged["work"]["model_logits_read"], 0)
                self.assertGreater(staged["work"]["native_state_bytes"], 0)
                self.assertIn("native_execute_ns", staged["timings"])
                self.assertEqual(
                    staged["admission"]["source_revision_id"],
                    executed["field_admission"]["source_revision_id"],
                )


class FieldOwnedEmissionTests(unittest.TestCase):
    def test_recalled_knowledge_reaches_the_emitter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outcomes = {}
            for color in ("ochre", "violet"):
                with CassiFieldWorkMemory(root / color) as memory:
                    memory.learn(fact(color, operation=color))
                    executed = memory.execute_native(
                        operation_id=f"emission-{color}",
                        instrument=instrument(),
                        mode="field",
                        prompt=PROMPT,
                        tokens=4,
                        sequence=1,
                        semantic_context=FACT_CONTEXT,
                    )
                    recall = executed["field_recall"]
                    self.assertEqual(recall["status"], "supported", recall)
                    self.assertEqual(len(recall["records"]), 1, recall)
                    self.assertEqual(recall["records"][0]["payload"]["color"], color)
                    frame = executed["emission_frame"]
                    self.assertEqual(frame["records_included"], 1, frame)
                    self.assertEqual(frame["records_dropped"], 0, frame)
                    self.assertEqual(frame["prompt_tokens"], executed["receipt"]["prompt_tokens"])
                    self.assertLessEqual(frame["prompt_tokens"], frame["token_ceiling"])
                    self.assertTrue(executed["field_admission"]["source_revision_id"])
                    outcomes[color] = {
                        "emission_prompt_sha256": executed["emission_prompt_sha256"],
                        "state": executed["state_successor"]["sha256"],
                        "output": executed["output"],
                        "record_sha256": recall["records"][0]["content_sha256"],
                    }
            with CassiFieldWorkMemory(root / "plain") as memory:
                control = memory.execute_native(
                    operation_id="emission-control",
                    instrument=instrument(),
                    mode="field",
                    prompt=PROMPT,
                    tokens=4,
                    sequence=1,
                )
                self.assertIsNone(control["field_recall"])
                self.assertIsNone(control["emission_frame"])
            self.assertNotEqual(
                outcomes["ochre"]["record_sha256"], outcomes["violet"]["record_sha256"]
            )
            self.assertNotEqual(
                outcomes["ochre"]["emission_prompt_sha256"],
                outcomes["violet"]["emission_prompt_sha256"],
                "recalled knowledge did not change the emitter input",
            )
            # Field-owned knowledge reaches the trial: each memory seats a
            # different field state, and both differ from a frame with no memory.
            self.assertNotEqual(
                outcomes["ochre"]["state"],
                outcomes["violet"]["state"],
                "recalled knowledge did not reach the field state",
            )
            self.assertNotEqual(
                outcomes["ochre"]["state"], control["state_successor"]["sha256"]
            )
            # The four-token greedy readout of the field does not separate these
            # two states; that is a measured limit of the readout, not of the route.
            self.assertEqual(outcomes["ochre"]["output"], outcomes["violet"]["output"])
            self.assertNotEqual(outcomes["ochre"]["output"], control["output"])

    def test_emitter_input_is_the_fixed_boundary_transducer(self) -> None:
        record = {
            "content_sha256": "a" * 64,
            "context": dict(FACT_CONTEXT),
            "payload": {"color": "ochre"},
            "source_id": "workshop.marker",
            "source_revision_id": "b" * 64,
        }
        composed = work_prompt(
            task=PROMPT, output_contract="contract", recall={"records": [record], "status": "supported"}
        )
        self.assertIn("FIELD_WORK_MEMORY", composed)
        self.assertIn("ochre", composed)
        # Provenance digests stay in the receipt: they cost more emitter tokens
        # than the fact itself and the emitter cannot use them.
        self.assertNotIn("a" * 64, composed)
        self.assertNotIn("b" * 64, composed)
        other = work_prompt(
            task=PROMPT,
            output_contract="contract",
            recall={"records": [{**record, "payload": {"color": "violet"}}], "status": "supported"},
        )
        self.assertNotEqual(composed, other)

    def test_frame_fitting_drops_records_it_cannot_fit(self) -> None:
        records = [
            {
                "content_sha256": "a" * 64,
                "context": dict(FACT_CONTEXT),
                "payload": {"color": f"color{index}"},
                "source_id": f"workshop.fact{index}",
                "source_revision_id": f"{index:064d}",
            }
            for index in range(6)
        ]
        calls = []

        def count(prompt: str) -> int:
            calls.append(prompt)
            return len(prompt)

        # The ceiling is measured in the runtime's tokens; this stub measures
        # characters so the fitting arithmetic is exercised without a runtime.
        ceiling = len(work_prompt(task=PROMPT, output_contract="contract", recall={"records": records[:3]}))
        frame = fit_emission_frame(
            task=PROMPT,
            output_contract="contract",
            recall={"records": records},
            token_ceiling=ceiling,
            count_tokens=count,
        )
        self.assertEqual(frame["prompt_tokens"], len(frame["prompt"]))
        self.assertLessEqual(frame["prompt_tokens"], ceiling)
        self.assertEqual(frame["records_included"], 3)
        self.assertEqual(frame["records_dropped"], 3)
        self.assertEqual(len(frame["dropped_source_revision_ids"]), 3)
        self.assertEqual(len(frame["included_source_revision_ids"]), 3)
        self.assertLessEqual(len(set(calls)), 5, "fitting should reuse measurements")

    def test_frame_segments_resolve_each_record_to_its_own_text(self) -> None:
        records = [
            {
                "content_sha256": "a" * 64,
                "context": dict(FACT_CONTEXT),
                "payload": {"color": f"color{index}"},
                "source_id": f"workshop.fact{index}",
                "source_revision_id": f"{index:064d}",
            }
            for index in range(3)
        ]
        frame = emission_frame(
            task=PROMPT,
            output_contract="contract",
            recall={"records": records, "status": "supported"},
        )
        prompt = frame["prompt"]
        self.assertEqual(
            frame["included_source_revision_ids"],
            [record["source_revision_id"] for record in records],
        )
        self.assertEqual(len(frame["segments"]), 3)
        for record, segment in zip(records, frame["segments"]):
            self.assertEqual(segment["source_revision_id"], record["source_revision_id"])
            text = prompt[segment["start"] : segment["stop"]]
            self.assertIn(record["source_id"], text)
            self.assertIn(record["payload"]["color"], text)
        memory = prompt[frame["memory_segment"]["start"] : frame["memory_segment"]["stop"]]
        self.assertTrue(memory.startswith("["))
        self.assertTrue(memory.endswith("]"))
        self.assertEqual(memory.count("source_id"), 3)

        def count(prompt_text: str) -> int:
            return len(prompt_text)

        measured = measure_segment_tokens(frame, count_tokens=count)
        token_starts = [segment["token_start"] for segment in measured]
        self.assertEqual(token_starts, sorted(token_starts))
        for segment in measured:
            self.assertLess(segment["token_start"], segment["token_stop"])
            self.assertEqual(
                segment["token_stop"],
                len(prompt[: segment["stop"]]),
            )
            self.assertEqual(
                segment["token_start"],
                len(prompt[: segment["start"]]),
            )

    def test_frame_memory_block_is_byte_identical_to_the_record_encoder(self) -> None:
        """The composed frame carries exactly the block the emitter always saw.

        Segment indexing must not perturb the prompt: if the memory block drifts
        by one byte, every measured workcase number describes a different input.
        """

        records = [
            {
                "content_sha256": "a" * 64,
                "context": dict(FACT_CONTEXT),
                "payload": {"color": f"color{index}"},
                "source_id": f"workshop.fact{index}",
                "source_revision_id": f"{index:064d}",
            }
            for index in range(3)
        ]
        frame = emission_frame(
            task=PROMPT,
            output_contract="contract",
            recall={"records": records, "status": "supported"},
        )
        prompt = frame["prompt"]
        expected = _encode_memory_block([emitter_record(record) for record in records])
        start = frame["memory_segment"]["start"]
        stop = frame["memory_segment"]["stop"]
        self.assertEqual(prompt[start:stop], expected)
        self.assertEqual(prompt.count(expected), 1)
        self.assertEqual(
            prompt,
            prompt[:start] + expected + prompt[stop:],
        )
        self.assertLess(prompt.index("authoritative when present"), start)
        # The task section follows the block immediately: no separator drift.
        self.assertEqual(prompt.index("\n\nTASK="), stop)
        self.assertEqual(work_prompt(task=PROMPT, output_contract="contract", recall={"records": records, "status": "supported"}), prompt)

    def test_frame_refuses_a_context_it_cannot_fit(self) -> None:
        with self.assertRaises(RuntimeError):
            fit_emission_frame(
                task=PROMPT,
                output_contract="contract",
                recall={"records": []},
                token_ceiling=1,
                count_tokens=lambda prompt: len(prompt),
            )
        with self.assertRaises(ValueError):
            fit_emission_frame(
                task=PROMPT,
                output_contract="contract",
                recall={"records": []},
                token_ceiling=0,
                count_tokens=lambda prompt: len(prompt),
            )


class NativeContinuationTests(unittest.TestCase):
    def test_capabilities_match_the_measured_trial_state(self) -> None:
        native = instrument()
        coupled = native.capabilities("coupled")
        field = native.capabilities("field")
        self.assertEqual(coupled.trial_state, "exact-context")
        self.assertTrue(coupled.supports("exact-native-resume"))
        self.assertEqual(field.trial_state, "exact-field-state")
        self.assertFalse(field.supports("exact-native-resume"))
        self.assertTrue(field.supports("exact-field-state"))
        self.assertEqual(native.continuation_class("field"), "field-only")
        self.assertEqual(native.continuation_class("coupled"), "exact-pair")
        degraded = instrument(native_context=False)
        self.assertEqual(degraded.capabilities("coupled").trial_state, "none")
        self.assertEqual(degraded.capabilities("coupled").native_persistence, "field-state")
        self.assertEqual(degraded.continuation_class("coupled"), "native-continuation-unavailable")
        with self.assertRaises(Exception):
            degraded.execute(
                mode="coupled",
                prompt="x",
                tokens=1,
                trial_dir=Path(tempfile.mkdtemp()) / "refused",
                context_in=STATE,
            )

    def test_full_context_snapshot_round_trips_across_processes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = instrument()
            first = native.execute(
                mode="coupled", prompt="The marker is", tokens=2, trial_dir=root / "first"
            )
            context = first["state_successor"]["native_context"]
            self.assertGreater(context["bytes"], first["state_successor"]["bytes"])
            self.assertEqual(context["restored_bytes"], 0)
            self.assertGreater(context["prompt_tokens"], 0)
            self.assertEqual(
                context["decoded_tokens"], context["prompt_tokens"] + 2
            )
            cold = native.execute(
                mode="coupled",
                prompt="The workshop answer is",
                tokens=2,
                trial_dir=root / "cold",
            )
            resumed = native.execute(
                mode="coupled",
                prompt="The workshop answer is",
                tokens=2,
                trial_dir=root / "resumed",
                context_in=Path(context["path"]),
            )
            replayed = native.execute(
                mode="coupled",
                prompt="The workshop answer is",
                tokens=2,
                trial_dir=root / "replayed",
                context_in=Path(context["path"]),
            )
            self.assertEqual(
                resumed["state_successor"]["native_context"]["restored_bytes"],
                context["bytes"],
            )
            self.assertEqual(resumed["output"], replayed["output"])
            self.assertEqual(
                resumed["state_successor"]["native_context"]["sha256"],
                replayed["state_successor"]["native_context"]["sha256"],
            )
            self.assertNotEqual(
                resumed["state_successor"]["native_context"]["sha256"],
                cold["state_successor"]["native_context"]["sha256"],
                "restored context did not affect the native successor state",
            )

    def test_continuation_receipt_binds_the_committed_instrument(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "owner"
            live = instrument()
            with CassiFieldWorkMemory(home) as memory:
                memory.execute_native(
                    operation_id="gate-trial",
                    instrument=live,
                    mode="coupled",
                    prompt="Give one word.",
                    tokens=2,
                    sequence=1,
                )
                receipt = memory.continuation_receipt(
                    "gate-trial", instrument=live, mode="coupled"
                )
                self.assertEqual(receipt["status"], "exact-pair", receipt)
                self.assertTrue(receipt["exact"], receipt)
                self.assertTrue(receipt["identity_matches"])
                self.assertEqual(receipt["committed_continuation_class"], "exact-pair")
                self.assertEqual(
                    receipt["instrument_identity_sha256"],
                    receipt["committed_identity_sha256"],
                )
                snapshot = Path(receipt["native_context"]["path"])
                self.assertTrue(snapshot.is_file())
                field_only = memory.continuation_receipt(
                    "gate-trial", instrument=live, mode="field"
                )
                self.assertFalse(field_only["exact"], field_only)
                self.assertEqual(field_only["mode"], "field")
                foreign = memory.continuation_receipt(
                    "gate-trial", instrument=instrument(native_context=False), mode="coupled"
                )
                self.assertFalse(foreign["exact"], foreign)
                self.assertFalse(foreign["identity_matches"])
                absent = memory.continuation_receipt(
                    "never-run", instrument=live, mode="coupled"
                )
                self.assertEqual(absent["status"], "transaction-missing", absent)
                self.assertFalse(absent["exact"])

    def test_recovery_requires_the_context_snapshot_to_survive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "owner"
            with CassiFieldWorkMemory(home) as memory:
                memory.execute_native(
                    operation_id="snapshot-trial",
                    instrument=instrument(),
                    mode="coupled",
                    prompt="Give one word.",
                    tokens=2,
                    sequence=1,
                )
                journal = CoupledTransactionJournal(home / "coupled-transactions")
                root = memory.owner.state.state_sha256
                self.assertEqual(journal.recover("snapshot-trial", field_root=root)["status"], "exact-pair")
                transaction = journal._read("snapshot-trial")
                Path(transaction["native_successor"]["native_context"]["path"]).unlink()
                self.assertEqual(
                    journal.recover("snapshot-trial", field_root=root)["status"],
                    "native-continuation-unavailable",
                )

    def test_receipt_declares_the_field_coupling_it_ran(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            native = instrument()
            coupled = native.execute(
                mode="coupled",
                prompt="Give one word.",
                tokens=2,
                trial_dir=Path(directory) / "coupled",
            )
            receipt = coupled["receipt"]
            # The default route is additive and keeps the native LM head.
            self.assertEqual(receipt["displacement"], 0, receipt)
            self.assertEqual(receipt["injection_scale"], 1.0, receipt)
            self.assertEqual(receipt["lm_head_owner"], "model", receipt)
            self.assertEqual(receipt["sampler_owner"], "native-llama", receipt)
            self.assertEqual(receipt["model_logits_read"], 2)
            self.assertEqual(receipt["field_logits_read"], 0)
            self.assertEqual(receipt["qwen_forward_passes"], 3)
            self.assertEqual(receipt["lm_head_rows_computed"], 3)
            self.assertEqual(receipt["lm_head_rows_skipped"], 0)
            field_only = native.execute(
                mode="field",
                prompt="Give one word.",
                tokens=2,
                trial_dir=Path(directory) / "field",
            )
            self.assertNotIn("displacement", field_only["receipt"])
            self.assertEqual(field_only["receipt"]["model_logits_read"], 0)
            self.assertEqual(field_only["receipt"]["field_logits_read"], 2)

    def test_declared_coupling_reaches_the_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            native = QwenNativeInstrument(
                executable=BINARY,
                model=MODEL,
                state=STATE,
                backend="cpu",
                coupling={"displacement": 0, "injection_scale": 30.0, "energy_floor": 0.0, "read_floor": 0.0},
            )
            receipt = native.execute(
                mode="coupled",
                prompt="Give one word.",
                tokens=2,
                trial_dir=Path(directory) / "coupled",
            )["receipt"]
            self.assertEqual(receipt["displacement"], 0, receipt)
            self.assertEqual(receipt["injection_scale"], 30.0, receipt)
            self.assertEqual(receipt["energy_floor"], 0.0, receipt)
            self.assertEqual(receipt["read_floor"], 0.0, receipt)
            # The coupling is part of what the instrument is, so a continuation
            # cannot silently change it.
            self.assertEqual(native.identity.as_dict()["coupling"]["displacement"], 0.0)
            self.assertNotEqual(native.identity.fingerprint, instrument().identity.fingerprint)

    def test_coupling_guard_rejects_a_receipt_that_disagrees(self) -> None:
        silent = instrument()
        defaults = {
            "displacement": 0,
            "injection_scale": 1.0,
            "energy_floor": 1e-6,
            "read_floor": 0.05,
        }
        silent._check_observed_coupling(defaults, "coupled")
        silent._check_observed_coupling(defaults, "field")
        silent._check_observed_coupling({}, "field")
        with self.assertRaisesRegex(RuntimeError, "omits coupling option read_floor"):
            silent._check_observed_coupling(
                {"displacement": 0, "injection_scale": 1.0, "energy_floor": 1e-6},
                "coupled",
            )
        observed_ownership = {
            "lm_head_owner": "model",
            "sampler_owner": "native-llama",
            "logit_owner": "model",
            "qwen_forward_passes": 3,
            "model_logits_read": 2,
            "field_logits_read": 0,
            "lm_head_rows_computed": 4,
            "lm_head_rows_skipped": 0,
            "sampler_steps": 2,
        }
        silent._check_observed_ownership(
            observed_ownership,
            silent.capabilities("coupled"),
        )
        with self.assertRaisesRegex(RuntimeError, "lm_head_owner"):
            silent._check_observed_ownership(
                {**observed_ownership, "lm_head_owner": "field"},
                silent.capabilities("coupled"),
            )

        native = QwenNativeInstrument(
            executable=BINARY,
            model=MODEL,
            state=STATE,
            backend="cpu",
            coupling={
                "displacement": 0,
                "injection_scale": 30.0,
                "energy_floor": 0.0,
                "read_floor": 0.0,
            },
        )
        native._check_observed_coupling(
            {
                "displacement": 0,
                "injection_scale": 30.0,
                "energy_floor": 0.0,
                "read_floor": 0.0,
            },
            "coupled",
        )
        with self.assertRaisesRegex(RuntimeError, "ran displacement 6, instrument declared 0"):
            native._check_observed_coupling(
                {**defaults, "displacement": 6}, "coupled"
            )
        with self.assertRaisesRegex(RuntimeError, "ran injection_scale 1.0"):
            native._check_observed_coupling(
                {**defaults, "injection_scale": 1.0, "energy_floor": 0.0, "read_floor": 0.0},
                "coupled",
            )

    def test_additive_field_correction_reaches_the_model(self) -> None:
        # The default route keeps the native LM head.  A larger gain remains
        # an explicit experiment rather than an implicit runtime default.
        def text(injection_scale: float) -> str:
            with tempfile.TemporaryDirectory() as directory:
                native = QwenNativeInstrument(
                    executable=BINARY,
                    model=MODEL,
                    state=STATE,
                    backend="cpu",
                    coupling={
                        "displacement": 0,
                        "injection_scale": injection_scale,
                        "energy_floor": 0.0,
                        "read_floor": 0.0,
                    },
                )
                return native.execute(
                    mode="coupled",
                    prompt=PROMPT,
                    tokens=8,
                    trial_dir=Path(directory) / "trial",
                )["output"]

        silent = text(1.0)
        self.assertEqual(text(0.0), silent)
        self.assertNotEqual(text(30.0), silent)

    def test_field_state_carries_content_without_claiming_semantic_readout(self) -> None:
        # State identity and exact-seed routing are observable; text inequality
        # from garbled output is not treated as a semantic conclusion.
        def composed(color: str) -> str:
            record = {
                "content_sha256": "a" * 64,
                "context": dict(FACT_CONTEXT),
                "payload": {"color": color},
                "source_id": "workshop.marker",
                "source_revision_id": "b" * 64,
            }
            return work_prompt(
                task=PROMPT,
                output_contract="Reply with the requested value only.",
                recall={"records": [record], "status": "supported"},
            )

        def seeded(color: str, directory: Path) -> Path:
            outcome = instrument().execute(
                mode="field",
                prompt=composed(color),
                tokens=1,
                trial_dir=directory / f"seed-{color}",
            )
            return Path(outcome["state_successor"]["path"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            states = {color: seeded(color, root) for color in ("amber", "olive")}
            self.assertNotEqual(
                hashlib.sha256(states["amber"].read_bytes()).hexdigest(),
                hashlib.sha256(states["olive"].read_bytes()).hexdigest(),
            )
            for color, state in states.items():
                native = QwenNativeInstrument(
                    executable=BINARY,
                    model=MODEL,
                    state=state,
                    backend="cpu",
                    coupling={"displacement": 0, "injection_scale": 1.0},
                )
                result = native.execute(
                    mode="coupled",
                    prompt=PROMPT,
                    tokens=2,
                    trial_dir=root / f"coupled-{color}",
                )
                self.assertEqual(
                    result["state_predecessor"]["sha256"],
                    hashlib.sha256(state.read_bytes()).hexdigest(),
                )

    def test_differential_native_trial_publishes_exact_seed_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "owner"
            with CassiFieldWorkMemory(home) as memory:
                memory.learn(fact("amber", operation="differential"))
                native = instrument()
                with self.assertRaisesRegex(ValueError, "coupled mode"):
                    memory.execute_native(
                        operation_id="field-differential-rejected",
                        instrument=native,
                        mode="field",
                        prompt=PROMPT,
                        tokens=2,
                        sequence=1,
                        differential_reference="What color is the reference marker?",
                    )
                reference_prompt = "What color is the reference marker?"
                executed = memory.execute_native(
                    operation_id="coupled-differential",
                    instrument=native,
                    mode="coupled",
                    prompt=PROMPT,
                    differential_reference=reference_prompt,
                    tokens=2,
                    sequence=2,
                    semantic_context={"kind": "workshop-fact", "topic": "marker"},
                )
                preparation = executed["differential_preparation"]
                self.assertEqual(
                    preparation["composition_method"],
                    "float32-elementwise-subtraction-experimental-contrast",
                )
                self.assertEqual(preparation["preparation_work"]["field_seed_runs"], 2)
                self.assertEqual(len(preparation["sources"]), 2)
                reference_source = next(
                    row for row in preparation["sources"] if row["role"] == "reference"
                )
                self.assertEqual(
                    reference_source["prompt_sha256"],
                    hashlib.sha256(reference_prompt.encode("utf-8")).hexdigest(),
                )
                self.assertEqual(
                    reference_source["prompt_bytes"],
                    len(reference_prompt.encode("utf-8")),
                )
                self.assertEqual(
                    executed["native_lineage"]["native_predecessor"]["sha256"],
                    preparation["state"]["sha256"],
                )
                self.assertEqual(len(executed["native_lineage"]["source_prompts"]), 2)
                self.assertEqual(executed["measured"]["differential_seed_runs"], 2)
                journal = CoupledTransactionJournal(home / "coupled-transactions")
                recovered = journal.recover(
                    "coupled-differential",
                    field_root=memory.owner.state.state_sha256,
                )
                self.assertEqual(recovered["status"], "exact-pair", recovered)
                self.assertEqual(
                    recovered["transaction"]["preparation"]["kind"],
                    "differential-field-state",
                )
                continuation = memory.continuation_receipt(
                    "coupled-differential",
                    instrument=native,
                    mode="coupled",
                )
                self.assertTrue(continuation["exact"], continuation)
                Path(preparation["state"]["path"]).unlink()
                self.assertEqual(
                    journal.recover(
                        "coupled-differential",
                        field_root=memory.owner.state.state_sha256,
                    )["status"],
                    "native-continuation-unavailable",
                )
                publication = journal.publication_status("coupled-differential")
                self.assertFalse(publication["eligible"], publication)
                self.assertEqual(publication["reason"], "preparation-artifact-unavailable")

    def test_differential_source_buffers_reject_corrupt_f32(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nonfinite = bytearray(STATE.read_bytes())
            struct.pack_into("<f", nonfinite, 0, float("nan"))
            for label, payload in (
                ("empty", b""),
                ("truncated", b"\x00"),
                ("nonfinite", bytes(nonfinite)),
            ):
                with self.subTest(label=label):
                    bad_seed = root / f"{label}.f32"
                    bad_seed.write_bytes(payload)
                    native = QwenNativeInstrument(
                        executable=BINARY, model=MODEL, state=bad_seed, backend="cpu"
                    )
                    destination = root / f"{label}-difference.f32"
                    with self.assertRaises(RuntimeError):
                        differential_field_state(
                            instrument=native,
                            frame="The marker is amber.",
                            reference="There is no marker observation.",
                            trial_dir=root / label,
                            output=destination,
                        )
                    self.assertFalse(destination.exists())

    def test_differential_seed_records_an_experimental_contrast(self) -> None:
        def composed(color: str) -> str:
            record = {
                "content_sha256": "a" * 64,
                "context": dict(FACT_CONTEXT),
                "payload": {"color": color},
                "source_id": "workshop.marker",
                "source_revision_id": "b" * 64,
            }
            return work_prompt(
                task=PROMPT,
                output_contract="Reply with the requested value only.",
                recall={"records": [record], "status": "supported"},
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = instrument()
            seed = differential_field_state(
                instrument=native,
                frame=composed("amber"),
                reference=composed("olive"),
                trial_dir=root / "seed",
                output=root / "differential.f32",
            )
            self.assertEqual(seed["schema"], "cassi.qwen-differential-field-state.v1")
            self.assertEqual(seed["composition_method"], "float32-elementwise-subtraction-experimental-contrast")
            self.assertEqual(seed["preparation_work"]["field_seed_runs"], 2)
            self.assertEqual(seed["original_seed"]["sha256"], hashlib.sha256(STATE.read_bytes()).hexdigest())
            self.assertEqual(len(seed["sources"]), 2)
            self.assertEqual(
                {row["role"] for row in seed["sources"]},
                {"frame", "reference"},
            )
            for row in seed["sources"]:
                self.assertEqual(len(row["prompt_sha256"]), 64)
                self.assertGreater(row["prompt_tokens"], 0)
                self.assertEqual(len(row["sha256"]), 64)
            self.assertGreater(seed["state"]["bytes"], 0)
            self.assertTrue(Path(seed["state"]["path"]).is_file())
            with self.assertRaises(FileExistsError):
                differential_field_state(
                    instrument=native,
                    frame=composed("amber"),
                    reference=composed("olive"),
                    trial_dir=root / "second-seed",
                    output=root / "differential.f32",
                )
            with self.assertRaisesRegex(ValueError, "two different prompts"):
                differential_field_state(
                    instrument=native,
                    frame=composed("amber"),
                    reference=composed("amber"),
                    trial_dir=root / "identical",
                    output=root / "identical.f32",
                )

    def test_journal_records_the_native_context_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "owner"
            with CassiFieldWorkMemory(home) as memory:
                executed = memory.execute_native(
                    operation_id="coupled-trial",
                    instrument=instrument(),
                    mode="coupled",
                    prompt="Give one word.",
                    tokens=2,
                    sequence=1,
                )
                self.assertEqual(executed["continuation_class"], "exact-pair")
                journal = CoupledTransactionJournal(home / "coupled-transactions")
                recovered = journal.recover(
                    "coupled-trial", field_root=memory.owner.state.state_sha256
                )
                self.assertEqual(recovered["status"], "exact-pair", recovered)
                descriptor = recovered["transaction"]["native_successor"]
                self.assertIsNotNone(descriptor["native_context"])
                self.assertEqual(
                    descriptor["kind"], "qi-field-state-and-native-context"
                )
                self.assertGreater(descriptor["native_context"]["bytes"], descriptor["bytes"])
                self.assertEqual(
                    recovered["transaction"]["continuation_class"], "exact-pair"
                )
                output_sha = executed["coupled_transaction"]["delivery"]["output_sha256"]
                self.assertEqual(len(output_sha), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
