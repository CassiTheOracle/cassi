import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from cassi_qi_field import QiFieldError
from cassi_task_receipts import (
    TaskCorpusEpisode,
    TaskObservation,
    TaskReceipt,
)
from cassi_universal_data import JournalReference

import run_general_task_gauntlet as gauntlet_module
from run_general_task_gauntlet import (
    _FieldOnlyRuntimeAudit,
    run_general_task_gauntlet,
)
from run_text_abstraction_comparison import (
    TextAbstractionController,
    TextProgram,
    TextToken,
)


def _episode(source_id: str, prompt: bytes, continuation: bytes) -> TaskCorpusEpisode:
    return TaskCorpusEpisode(
        source_id=source_id,
        prompt=prompt,
        continuation=continuation,
        payload_sha256=hashlib.sha256(prompt + continuation).hexdigest(),
    )


def test_canonical_task_types_reject_bad_digests_and_references() -> None:
    with pytest.raises(ValueError, match="payload_sha256"):
        TaskCorpusEpisode(
            source_id="source",
            prompt=b"prompt",
            continuation=b"continuation",
            payload_sha256="0" * 64,
        )

    reference = JournalReference(
        packet_sha256="1" * 64,
        packet_object_sha256="2" * 64,
        payload_manifest_sha256="3" * 64,
        journal_head_sha256="4" * 64,
        source_stream_id="stream",
        source_sequence=0,
    )
    with pytest.raises(ValueError, match="reference packet digest"):
        TaskObservation(
            episode_id="episode",
            source_id="source",
            split="training",
            codec_id="codec",
            prompt=b"prompt",
            packet_sha256="5" * 64,
            view_sha256="6" * 64,
            reference=reference,
        )
    with pytest.raises(ValueError, match="counts and accuracy"):
        TaskReceipt(
            family="family",
            status="exhausted",
            program_sha256=None,
            tokens=(),
            exact=1,
            total=2,
            accuracy=0.25,
        )


def test_field_only_runtime_audit_blocks_subprocess_access() -> None:
    audit = _FieldOnlyRuntimeAudit()
    with pytest.raises(QiFieldError, match="blocked subprocess access"):
        with audit:
            subprocess.Popen([b"forbidden"])
    assert audit.subprocess_attempts == 1


def test_reproduction_phase_derives_failure_from_entrypoint_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        gauntlet_module,
        "run_text_abstraction_comparison",
        lambda: {"result": "TEXT_ABSTRACTION_COMPARISON_FAILED"},
    )
    monkeypatch.setattr(
        gauntlet_module,
        "run_generative_abstraction_scenario",
        lambda: {
            "result": "GENERATIVE_ABSTRACTION_OK",
            "candidate_count": 12,
        },
    )
    monkeypatch.setattr(
        gauntlet_module,
        "run_universal_data_field_scenario",
        lambda: {"result": "UNIVERSAL_DATA_FIELD_OK"},
    )

    result = gauntlet_module.run_gauntlet_phase("reproduction")

    assert result["diagnostic_checks_passed"] is False
    assert result["reproduction"]["success"] == {
        "text_abstraction": False,
        "generative_abstraction": True,
        "universal_data_field": True,
    }


def test_cli_persists_receipt_and_distinguishes_readiness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt = {
        "schema": "cassi.general-task-gauntlet-result.v2",
        "phase": "controls",
        "execution_scope": "full_prerequisite_chain",
        "metrics": {
            "readiness": {
                "status": "not_ready",
                "missing": ["learned_cross_view_transfer"],
            }
        },
        "field_only": {
            "mode": "enforced_runtime_sentinels",
            "device": "cpu",
        },
        "diagnostic_checks_passed": True,
        "readiness_validated": False,
    }
    dispatched: list[str] = []

    def run_phase(phase: str) -> dict[str, object]:
        dispatched.append(phase)
        return receipt

    monkeypatch.setattr(gauntlet_module, "run_gauntlet_phase", run_phase)
    output = tmp_path / "receipt.json"

    exit_code = gauntlet_module.main(
        [
            "--phase",
            "controls",
            "--output",
            str(output),
            "--require-ready",
        ]
    )

    assert exit_code == 2
    assert dispatched == ["controls"]
    assert json.loads(output.read_text(encoding="utf-8")) == receipt

    failed_receipt = {
        **receipt,
        "phase": "reproduction",
        "diagnostic_checks_passed": False,
    }

    def run_failed_phase(phase: str) -> dict[str, object]:
        dispatched.append(phase)
        return failed_receipt

    monkeypatch.setattr(
        gauntlet_module,
        "run_gauntlet_phase",
        run_failed_phase,
    )
    failed_output = tmp_path / "failed-receipt.json"
    failed_exit_code = gauntlet_module.main(
        [
            "--phase",
            "reproduction",
            "--output",
            str(failed_output),
        ]
    )

    assert failed_exit_code == 1
    assert dispatched == ["controls", "reproduction"]
    assert json.loads(failed_output.read_text(encoding="utf-8")) == failed_receipt


def test_single_regime_update_preserves_every_other_field_namespace() -> None:
    programs = (
        TextProgram((TextToken.PROMPT, TextToken.FIT)),
        TextProgram((TextToken.PROMPT, TextToken.ASCII_UPPER, TextToken.FIT)),
        TextProgram((TextToken.PROMPT, TextToken.REVERSE_BYTES, TextToken.FIT)),
    )
    controller = TextAbstractionController(
        programs=programs,
        regimes=("upper", "reverse"),
        grammar_id="test-sequential-regime-updates-v1",
    )
    prompts = (b"Alpha beta 123", b"Mixed CASE sample")
    upper_examples = tuple((prompt, prompt.upper()) for prompt in prompts)
    reverse_examples = tuple((prompt, prompt[::-1]) for prompt in prompts)

    upper_state = controller.learn_regime(
        controller.new_state(),
        "upper",
        upper_examples,
    )
    upper_state_sha256 = controller.state_sha256(upper_state)
    upper_namespace_sha256 = controller.regime_sha256(upper_state, "upper")
    upper_records = controller.records(upper_state, "upper")
    upper_selection = controller.select(upper_state, "upper")

    final_state = controller.learn_regime(upper_state, "reverse", reverse_examples)

    assert controller.state_sha256(upper_state) == upper_state_sha256
    assert controller.regime_sha256(final_state, "upper") == upper_namespace_sha256
    assert controller.records(final_state, "upper") == upper_records
    assert controller.select(final_state, "upper") == upper_selection
    assert upper_selection.status == "selected"
    assert controller.select(final_state, "reverse").status == "selected"
    assert controller.state_sha256(final_state) == controller.state_sha256(
        controller.synthesize(
            {
                "upper": upper_examples,
                "reverse": reverse_examples,
            }
        )
    )


def test_general_task_gauntlet_covers_curriculum_and_negative_controls() -> None:
    training = (
        _episode(
            "training-a",
            b"Alice carefully trusts Bob because Carol calmly helps Dave today.",
            b"observed outcome alpha!",
        ),
        _episode(
            "training-a",
            b"Eve boldly follows Frank while Grace gently guides Heidi home.",
            b"measured result beta??",
        ),
        _episode(
            "training-b",
            b"Ivan quietly greets Judy after Karl swiftly finds Lena outside.",
            b"independent answer gamma",
        ),
        _episode(
            "training-b",
            b"Mallory warmly thanks Niaj before Olivia clearly assists Peggy again.",
            b"unrelated response delta",
        ),
    )
    holdout = (
        _episode(
            "holdout",
            b"Quinn softly visits Ruth because Sybil brightly welcomes Trent inside.",
            b"held out continuation one",
        ),
        _episode(
            "holdout",
            b"Uma quickly calls Victor while Wendy patiently advises Xavier nearby.",
            b"held out continuation two",
        ),
        _episode(
            "holdout",
            b"Yvonne calmly meets Zach after Amber kindly directs Blake onward.",
            b"held out continuation three",
        ),
        _episode(
            "holdout",
            b"Cora firmly asks Diego before Elena wisely answers Farah today.",
            b"held out continuation four",
        ),
    )

    result = run_general_task_gauntlet(
        training,
        holdout,
        holdout_source="holdout",
        long_horizon_updates=16,
    )

    assert result["diagnostic_checks_passed"] is True
    assert result["readiness_validated"] is False
    assert result["reproduction"] == {
        "status": "not_run",
        "reason": "custom_corpus",
    }
    assert result["corpus"]["source_disjoint"] is True
    assert result["corpus"]["episode_disjoint"] is True
    assert result["corpus"]["training_episodes"] == 4
    assert result["corpus"]["holdout_episodes"] == 4
    assert result["corpus"]["raw_receipt_source_overlap"] == []
    assert result["corpus"]["selected_split_source_overlap"] == []
    assert result["corpus"]["split_strategy"] == "leave_one_source_out"
    assert result["candidate_space"]["kind"] == "bounded_fixed_program_grammar"
    assert result["candidate_space"]["task_independent_learner"] is False
    assert result["candidate_space"]["semantic_acquisition"] is False
    assert all(
        receipt["status"] == "exhausted" and receipt["accuracy"] == 0.0
        for receipt in result["baseline"].values()
    )
    assert len(result["families"]) == 13
    assert all(
        receipt["status"] == "selected" and receipt["accuracy"] == 1.0
        for receipt in result["families"].values()
    )
    assert result["retention"]["minimum_accuracy"] == 1.0
    assert result["retention"]["maximum_accuracy_drop"] == 0.0
    assert all(
        receipt["accuracy"] == 1.0
        and receipt["trained_directly"] is False
        for receipt in result["transfer"]["cross_task_composition"].values()
    )
    assert all(
        receipt["accuracy"] == 1.0
        for receipt in result["transfer"]["codec_invariance"].values()
    )
    assert result["transfer"]["learned_cross_view"] == {
        "status": "unsupported",
        "reason": "fixed_projection_only",
    }
    assert result["controls"]["natural"]["status"] == "exhausted"
    assert result["controls"]["ambiguous"]["status"] == "ambiguous"
    assert result["controls"]["shuffled_outcomes"]["status"] == "exhausted"
    assert (
        result["controls"]["field_lesion"]["selection_after"]["status"]
        == "exhausted"
    )
    assert result["controls"]["field_lesion"]["unrelated_family_accuracy"] == 1.0
    assert result["controls"]["unsupported"]["status"] == "unsupported"
    assert result["controls"]["unsupported"]["adaptive_state_changed"] is False
    assert result["field"] == {
        **result["field"],
        "checkpoint_reload_exact": True,
        "inference_preserved_state": True,
        "long_horizon_updates": 16,
        "device": "cpu",
        "long_horizon_fixed_point": True,
    }
    assert result["ingress"]["restart_replay_exact"] is True
    assert len(result["ingress"]["holdout_codecs"]) == 4
    field_only = result["field_only"]
    assert field_only["mode"] == "enforced_runtime_sentinels"
    assert field_only["device"] == "cpu"
    assert field_only["adaptive_field_states"] == 1
    assert field_only["teacher_calls"] == 0
    assert field_only["qwen_calls"] == 0
    assert field_only["optimizer_steps"] == 0
    assert field_only["forbidden_import_attempts"] == 0
    assert field_only["subprocess_attempts"] == 0
    assert field_only["socket_attempts"] == 0
    assert field_only["optimizer_attempts"] == 0
    assert field_only["preloaded_forbidden_modules"] == []
    assert result["readiness"] == {
        "status": "not_ready",
        "missing": ["learned_cross_view_transfer"],
    }
