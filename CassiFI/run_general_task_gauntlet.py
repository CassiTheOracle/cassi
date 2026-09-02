from __future__ import annotations

import argparse
import builtins
from contextlib import ExitStack
import base64
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import socket
import subprocess
import sys
from typing import Any, Literal, Mapping, Sequence
from unittest.mock import patch

import torch

from cassi_qi_field import QiFieldError, QiFieldState
from cassi_task_receipts import (
    TaskCorpusEpisode,
    TaskEpisode,
    TaskObservation,
    TaskReceipt,
)
from cassi_universal_data import (
    BoundaryIdentity,
    BoundaryPacket,
    CODEC_JSON,
    CODEC_OPAQUE,
    CODEC_TENSOR,
    CODEC_TEXT,
    ObservationView,
    QiIngressJournal,
    adapt,
)
from run_generative_abstraction import (
    run_generative_abstraction_scenario,
    run_universal_data_field_scenario,
)
from run_text_abstraction_comparison import (
    CORPUS_ARTIFACT,
    ROOT,
    RoleProgram,
    TextAbstractionController,
    TextProgram,
    TextSelection,
    TextToken,
    _load_episode,
    _role_control_programs,
    evaluate_role_program,
    evaluate_text_program,
    generate_role_programs,
    generate_text_programs,
    run_text_abstraction_comparison,
)


RESULT_SCHEMA = "cassi.general-task-gauntlet-result.v2"
DEFAULT_RECEIPT = (
    ROOT / "artifacts" / "general-task-gauntlet" / "receipt.json"
)
STATE_MAGIC = b"CASSI-GENERAL-TASK-GAUNTLET-2\0"
_FORBIDDEN_RUNTIME_MODULE_ROOTS = ("llama_cpp", "openai", "transformers")


class _FieldOnlyRuntimeAudit:
    def __init__(self) -> None:
        self.forbidden_import_attempts = 0
        self.subprocess_attempts = 0
        self.socket_attempts = 0
        self.optimizer_attempts = 0
        self.preloaded_forbidden_modules: tuple[str, ...] = ()
        self.environment_keys = tuple(
            sorted(
                key
                for key in os.environ
                if any(token in key.upper() for token in ("QWEN", "LLAMA", "OPENAI"))
            )
        )
        self._stack: ExitStack | None = None

    def _deny(self, kind: str) -> None:
        if kind == "import":
            self.forbidden_import_attempts += 1
        elif kind == "subprocess":
            self.subprocess_attempts += 1
        elif kind == "socket":
            self.socket_attempts += 1
        elif kind == "optimizer":
            self.optimizer_attempts += 1
        raise QiFieldError(f"field-only gauntlet blocked {kind} access")

    def __enter__(self) -> _FieldOnlyRuntimeAudit:
        self.preloaded_forbidden_modules = tuple(
            sorted(
                {
                    name.partition(".")[0]
                    for name in sys.modules
                    if name.partition(".")[0] in _FORBIDDEN_RUNTIME_MODULE_ROOTS
                }
            )
        )
        if self.preloaded_forbidden_modules:
            raise QiFieldError(
                "field-only gauntlet found a preloaded forbidden inference module"
            )

        stack = ExitStack()
        original_import = builtins.__import__

        def guarded_import(
            name: str,
            globals: Mapping[str, Any] | None = None,
            locals: Mapping[str, Any] | None = None,
            fromlist: Sequence[str] = (),
            level: int = 0,
        ) -> Any:
            if name.partition(".")[0] in _FORBIDDEN_RUNTIME_MODULE_ROOTS:
                self._deny("import")
            return original_import(name, globals, locals, fromlist, level)

        def block_subprocess(*_args: Any, **_kwargs: Any) -> None:
            self._deny("subprocess")

        def block_socket(*_args: Any, **_kwargs: Any) -> None:
            self._deny("socket")

        def block_optimizer(*_args: Any, **_kwargs: Any) -> None:
            self._deny("optimizer")

        stack.enter_context(patch.object(builtins, "__import__", guarded_import))
        stack.enter_context(patch.object(subprocess, "Popen", block_subprocess))
        stack.enter_context(patch.object(os, "system", block_subprocess))
        stack.enter_context(patch.object(socket, "socket", block_socket))
        stack.enter_context(patch.object(socket, "create_connection", block_socket))
        stack.enter_context(
            patch.object(torch.optim.Optimizer, "__init__", block_optimizer)
        )
        for candidate in vars(torch.optim).values():
            if (
                isinstance(candidate, type)
                and issubclass(candidate, torch.optim.Optimizer)
                and "step" in candidate.__dict__
            ):
                stack.enter_context(
                    patch.object(candidate, "step", block_optimizer)
                )
        self._stack = stack
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: Any,
    ) -> None:
        if self._stack is not None:
            self._stack.close()
            self._stack = None

    def receipt(self) -> dict[str, Any]:
        return {
            "mode": "enforced_runtime_sentinels",
            "device": "cpu",
            "adaptive_field_states": 1,
            "teacher_calls": 0,
            "qwen_calls": 0,
            "optimizer_steps": 0,
            "forbidden_import_attempts": self.forbidden_import_attempts,
            "subprocess_attempts": self.subprocess_attempts,
            "socket_attempts": self.socket_attempts,
            "optimizer_attempts": self.optimizer_attempts,
            "preloaded_forbidden_modules": list(
                self.preloaded_forbidden_modules
            ),
            "qwen_environment_keys": list(self.environment_keys),
            "sentinels": [
                "forbidden_imports",
                "subprocess",
                "socket",
                "torch_optimizer",
            ],
        }
_TEXT_PREFIX = b"Aa Bb Cc 0123456789 | "
_HOLDOUT_CODECS = (CODEC_JSON, CODEC_TENSOR, CODEC_OPAQUE, CODEC_TEXT)
_TEXT_FAMILY_TOKENS: Mapping[str, tuple[TextToken, ...]] = {
    "identity": (TextToken.PROMPT, TextToken.FIT),
    "ascii_upper": (
        TextToken.PROMPT,
        TextToken.ASCII_UPPER,
        TextToken.FIT,
    ),
    "ascii_lower": (
        TextToken.PROMPT,
        TextToken.ASCII_LOWER,
        TextToken.FIT,
    ),
    "ascii_swapcase": (
        TextToken.PROMPT,
        TextToken.ASCII_SWAPCASE,
        TextToken.FIT,
    ),
    "reverse_bytes": (
        TextToken.PROMPT,
        TextToken.REVERSE_BYTES,
        TextToken.FIT,
    ),
    "reverse_words": (
        TextToken.PROMPT,
        TextToken.REVERSE_WORDS,
        TextToken.FIT,
    ),
    "suffix1": (
        TextToken.PROMPT,
        TextToken.SUFFIX_1,
        TextToken.REPEAT_TO_LENGTH,
    ),
    "suffix2": (
        TextToken.PROMPT,
        TextToken.SUFFIX_2,
        TextToken.REPEAT_TO_LENGTH,
    ),
    "suffix4": (
        TextToken.PROMPT,
        TextToken.SUFFIX_4,
        TextToken.REPEAT_TO_LENGTH,
    ),
    "suffix8": (
        TextToken.PROMPT,
        TextToken.SUFFIX_8,
        TextToken.REPEAT_TO_LENGTH,
    ),
}
_ROLE_FAMILIES = ("entity_swap", "predicate_rebind", "discourse_reverse")
_SUPPORTED_FAMILIES = (*_TEXT_FAMILY_TOKENS, *_ROLE_FAMILIES)
_CONTROL_FAMILIES = (*_SUPPORTED_FAMILIES, "natural", "ambiguous_case")
_TRANSFER_TASKS: Mapping[str, tuple[str, ...]] = {
    "upper_then_reverse_words": ("ascii_upper", "reverse_words"),
    "swapcase_involution": ("ascii_swapcase", "ascii_swapcase"),
    "suffix2_then_upper": ("suffix2", "ascii_upper"),
}




def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_default_episodes() -> tuple[tuple[TaskCorpusEpisode, ...], tuple[TaskCorpusEpisode, ...]]:
    training_receipt = json.loads(
        (CORPUS_ARTIFACT / "training-receipt.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "configs" / "cassi-qi-corpus-first-wave.json").read_text(
            encoding="utf-8"
        )
    )
    source_paths = {
        str(source["id"]): Path(str(source["path"]))
        for source in manifest["sources"]
    }
    experience = training_receipt["experience"]
    training = tuple(
        _load_episode(descriptor, source_paths)
        for descriptor in experience["training_episodes"]
    )
    holdout = tuple(
        _load_episode(descriptor, source_paths)
        for descriptor in experience["heldout_episodes"]
    )
    return training, holdout


def _program_catalog() -> tuple[tuple[Any, ...], dict[str, Any]]:
    text_programs = generate_text_programs()
    role_programs = generate_role_programs()
    text_by_tokens = {program.tokens: program for program in text_programs}
    controls: dict[str, Any] = {
        family: text_by_tokens[tokens]
        for family, tokens in _TEXT_FAMILY_TOKENS.items()
    }
    controls.update(_role_control_programs(role_programs))
    programs: tuple[Any, ...] = (*text_programs, *role_programs)
    if len({program.sha256 for program in programs}) != len(programs):
        raise QiFieldError("general-task program identities collide")
    return programs, controls


def _evaluate_program(program: Any, prompt: bytes, length: int) -> bytes:
    if isinstance(program, TextProgram):
        return evaluate_text_program(program, prompt, length)
    if isinstance(program, RoleProgram):
        return evaluate_role_program(program, prompt, length)
    raise QiFieldError("general-task field selected an unsupported program")


def _payload_for_codec(prompt: bytes, codec_id: str) -> bytes:
    if codec_id == CODEC_JSON:
        return _canonical_bytes(
            {"prompt_base64": base64.b64encode(prompt).decode("ascii")}
        )
    return prompt


def _project_prompt(view: ObservationView, codec_id: str) -> bytes:
    payload = view.round_trip()
    if codec_id == CODEC_JSON:
        parsed = json.loads(payload)
        if not isinstance(parsed, dict) or set(parsed) != {"prompt_base64"}:
            raise QiFieldError("general-task JSON projection changed shape")
        encoded = parsed["prompt_base64"]
        if not isinstance(encoded, str):
            raise QiFieldError("general-task JSON prompt is not base64 text")
        try:
            prompt = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise QiFieldError("general-task JSON prompt is invalid base64") from error
        if base64.b64encode(prompt).decode("ascii") != encoded:
            raise QiFieldError("general-task JSON prompt is noncanonical base64")
        return prompt
    return payload


def _ingest_observations(
    journal: QiIngressJournal,
    episodes: Sequence[TaskCorpusEpisode],
    *,
    split: Literal["training", "holdout"],
    profile_sha256: str,
) -> tuple[TaskObservation, ...]:
    observations = []
    for index, episode in enumerate(episodes):
        codec_id = (
            CODEC_TEXT
            if split == "training"
            else _HOLDOUT_CODECS[index % len(_HOLDOUT_CODECS)]
        )
        payload = _payload_for_codec(episode.prompt, codec_id)
        episode_id = f"{split}-{index}-{episode.payload_sha256[:16]}"
        packet = BoundaryPacket.create(
            identity=BoundaryIdentity(
                run_id="general-task-gauntlet",
                episode_id=episode_id,
                world_id="mixed-corpus",
                session_id="general-task-gauntlet",
                profile_sha256=profile_sha256,
                clock_sha256=profile_sha256,
                source_epoch="frozen-corpus-split-v1",
                source_stream_id=f"general-task:{split}",
                body_frame_id="corpus-prompt",
            ),
            codec_id=codec_id,
            request_id=f"observe-{episode_id}",
            logical_tick=index,
            logical_time=Fraction(index, 1),
            capture_start=Fraction(index, 1),
            capture_end=Fraction(index, 1),
            source_sequence=index,
            payload_shape=(len(payload),),
            payload_dtype="uint8",
            payload=payload,
            ingress_journal_sha256=journal.head_sha256,
        )
        reference = journal.append(packet)
        result = adapt(packet, codec_id, evidence=(reference,))
        if result.status != "selected" or result.value is None:
            raise QiFieldError(
                f"general-task observation adapter abstained: {result.reason}"
            )
        prompt = _project_prompt(result.value, codec_id)
        if prompt != episode.prompt:
            raise QiFieldError("general-task observation projection changed bytes")
        observations.append(
            TaskObservation(
                episode_id=episode_id,
                source_id=episode.source_id,
                split=split,
                codec_id=codec_id,
                prompt=prompt,
                packet_sha256=reference.packet_sha256,
                view_sha256=result.value.view_sha256,
                reference=reference,
            )
        )
    return tuple(observations)


def _family_prompt(family: str, prompt: bytes) -> bytes:
    if family in _TEXT_FAMILY_TOKENS:
        return _TEXT_PREFIX + prompt
    if family == "ambiguous_case":
        return (_TEXT_PREFIX + prompt).lower()
    return prompt


def _task_episodes(
    observations: Sequence[TaskObservation],
    corpus: Sequence[TaskCorpusEpisode],
    controls: Mapping[str, Any],
) -> dict[str, tuple[TaskEpisode, ...]]:
    if len(observations) != len(corpus):
        raise QiFieldError("general-task observation and corpus counts differ")
    result: dict[str, tuple[TaskEpisode, ...]] = {}
    for family in _CONTROL_FAMILIES:
        rows = []
        for observation, source in zip(observations, corpus, strict=True):
            prompt = _family_prompt(family, observation.prompt)
            if family == "natural":
                target = source.continuation
            elif family == "ambiguous_case":
                target = evaluate_text_program(
                    controls["ascii_upper"],
                    prompt,
                    len(source.continuation),
                )
            else:
                target = _evaluate_program(
                    controls[family],
                    prompt,
                    len(source.continuation),
                )
            if not prompt or not target:
                raise QiFieldError("general-task episode contains an empty span")
            rows.append(
                TaskEpisode(
                    episode_id=f"{observation.episode_id}:{family}",
                    family=family,
                    split=observation.split,
                    source_id=observation.source_id,
                    codec_id=observation.codec_id,
                    packet_sha256=observation.packet_sha256,
                    view_sha256=observation.view_sha256,
                    reference=observation.reference,
                    prompt=prompt,
                    target=target,
                )
            )
        result[family] = tuple(rows)
    return result


def _training_examples(
    episodes: Sequence[TaskEpisode],
    holdout_source: str,
) -> tuple[tuple[bytes, bytes], ...]:
    if any(
        episode.split != "training" or episode.source_id == holdout_source
        for episode in episodes
    ):
        raise QiFieldError("holdout episode reached the training path")
    return tuple((episode.prompt, episode.target) for episode in episodes)


def _evaluate_family(
    controller: TextAbstractionController,
    state: QiFieldState,
    family: str,
    episodes: Sequence[TaskEpisode],
) -> TaskReceipt:
    selection = controller.select(state, family)
    program = controller.selected_program(state, family)
    exact = 0
    if program is not None:
        exact = sum(
            _evaluate_program(program, episode.prompt, len(episode.target))
            == episode.target
            for episode in episodes
        )
    return TaskReceipt(
        family=family,
        status=selection.status,
        program_sha256=selection.program_sha256,
        tokens=selection.tokens,
        exact=exact,
        total=len(episodes),
        accuracy=exact / len(episodes),
    )


def _selection_payload(selection: TextSelection) -> dict[str, Any]:
    return {
        "status": selection.status,
        "program_id": selection.program_id,
        "program_sha256": selection.program_sha256,
        "tokens": list(selection.tokens),
        "equivalent_program_ids": list(selection.equivalent_program_ids),
        "score": selection.score,
        "margin": selection.margin,
    }


def _composition_receipts(
    controller: TextAbstractionController,
    state: QiFieldState,
    holdout: Mapping[str, Sequence[TaskEpisode]],
    controls: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    receipts = {}
    for name, families in _TRANSFER_TASKS.items():
        learned = tuple(controller.selected_program(state, family) for family in families)
        if any(program is None for program in learned):
            raise QiFieldError(f"general-task transfer primitive is unavailable: {name}")
        episodes = holdout[families[0]]
        exact = 0
        for episode in episodes:
            predicted = episode.prompt
            expected = episode.prompt
            for learned_program, family in zip(learned, families, strict=True):
                if learned_program is None:
                    raise QiFieldError("general-task transfer program disappeared")
                predicted = _evaluate_program(
                    learned_program,
                    predicted,
                    len(episode.target),
                )
                expected = _evaluate_program(
                    controls[family],
                    expected,
                    len(episode.target),
                )
            exact += predicted == expected
        receipts[name] = {
            "families": list(families),
            "exact": exact,
            "total": len(episodes),
            "accuracy": exact / len(episodes),
            "trained_directly": False,
        }
    return receipts


def _append_malformed_control(
    journal: QiIngressJournal,
    profile_sha256: str,
) -> dict[str, Any]:
    index = len(journal.replay())
    packet = BoundaryPacket.create(
        identity=BoundaryIdentity(
            run_id="general-task-gauntlet",
            episode_id="malformed-text-control",
            world_id="mixed-corpus",
            session_id="general-task-gauntlet",
            profile_sha256=profile_sha256,
            clock_sha256=profile_sha256,
            source_epoch="malformed-control-v1",
            source_stream_id="general-task:malformed",
            body_frame_id="corpus-prompt",
        ),
        codec_id=CODEC_TEXT,
        request_id="observe-malformed-text",
        logical_tick=index,
        logical_time=Fraction(index, 1),
        capture_start=Fraction(index, 1),
        capture_end=Fraction(index, 1),
        source_sequence=0,
        payload_shape=(1,),
        payload_dtype="uint8",
        payload=b"\xff",
        ingress_journal_sha256=journal.head_sha256,
    )
    reference = journal.append(packet)
    result = adapt(packet, CODEC_TEXT, evidence=(reference,))
    if result.status != "unsupported" or result.reason != "malformed_input":
        raise QiFieldError("general-task malformed adapter control settled")
    return {
        "status": result.status,
        "reason": result.reason,
        "packet_sha256": reference.packet_sha256,
        "journal_head_sha256": reference.journal_head_sha256,
        "adaptive_state_changed": False,
    }
def _reproduce_existing_entrypoints() -> dict[str, Any]:
    text = run_text_abstraction_comparison()
    generative = run_generative_abstraction_scenario()
    universal = run_universal_data_field_scenario()
    expected_results = {
        "text_abstraction": "TEXT_ABSTRACTION_COMPARISON_OK",
        "generative_abstraction": "GENERATIVE_ABSTRACTION_OK",
        "universal_data_field": "UNIVERSAL_DATA_FIELD_OK",
    }
    observed_results = {
        "text_abstraction": text.get("result"),
        "generative_abstraction": generative.get("result"),
        "universal_data_field": universal.get("result"),
    }
    success = {
        name: observed_results[name] == expected
        for name, expected in expected_results.items()
    }
    return {
        "expected_results": expected_results,
        "observed_results": observed_results,
        "success": success,
        "diagnostic_checks_passed": all(success.values()),
        "text_abstraction": {
            "entrypoint": "run_text_abstraction_comparison",
            "candidate_space": {
                "kind": "bounded_fixed_program_grammar",
                "task_independent_learner": False,
                "semantic_acquisition": False,
            },
            "receipt": {
                key: value
                for key, value in text.items()
                if key != "examples"
            },
        },
        "generative_abstraction": {
            "entrypoint": "run_generative_abstraction_scenario",
            "candidate_space": {
                "kind": "bounded_typed_grammar",
                "task_independent_learner": False,
                "semantic_acquisition": False,
                "candidate_count": generative["candidate_count"],
            },
            "receipt": {
                key: value
                for key, value in generative.items()
                if key != "program_evidence"
            },
        },
        "universal_data_field": {
            "entrypoint": "run_universal_data_field_scenario",
            "candidate_space": {
                "kind": "bounded_typed_relational_grammar",
                "task_independent_learner": False,
                "cross_view_scope": "registered_relational_task_only",
            },
            "receipt": universal,
        },
    }




def _run_general_task_gauntlet(
    training: Sequence[TaskCorpusEpisode] | None = None,
    holdout: Sequence[TaskCorpusEpisode] | None = None,
    *,
    holdout_source: str | None = None,
    long_horizon_updates: int = 256,
) -> dict[str, Any]:
    if (training is None) != (holdout is None):
        raise QiFieldError("training and holdout must be supplied together")
    if training is None or holdout is None:
        training, holdout = _load_default_episodes()
    training = tuple(training)
    holdout = tuple(holdout)
    if not training or not holdout or long_horizon_updates < 1:
        raise QiFieldError("general-task gauntlet inputs are incomplete")
    holdout_sources = sorted({episode.source_id for episode in holdout})
    selected_holdout_source = holdout_source or holdout_sources[-1]
    source_disjoint_training = tuple(
        episode for episode in training if episode.source_id != selected_holdout_source
    )
    source_disjoint_holdout = tuple(
        episode for episode in holdout if episode.source_id == selected_holdout_source
    )
    if not source_disjoint_training or not source_disjoint_holdout:
        raise QiFieldError("general-task source-disjoint split is empty")
    if {episode.source_id for episode in source_disjoint_training} & {
        episode.source_id for episode in source_disjoint_holdout
    }:
        raise QiFieldError("general-task source-disjoint split overlaps")
    if {episode.payload_sha256 for episode in training} & {
        episode.payload_sha256 for episode in holdout
    }:
        raise QiFieldError("general-task corpus episodes overlap")

    programs, controls = _program_catalog()
    candidate_space = {
        "kind": "bounded_fixed_program_grammar",
        "task_independent_learner": False,
        "semantic_acquisition": False,
        "selection": "enumerate_score_select",
        "namespaces": {
            "cassi.text-program.v1": sum(
                isinstance(program, TextProgram) for program in programs
            ),
            "cassi.surface-role-program.v1": sum(
                isinstance(program, RoleProgram) for program in programs
            ),
        },
        "family_namespaces": {
            family: (
                "cassi.text-program.v1"
                if family in _TEXT_FAMILY_TOKENS
                else "cassi.surface-role-program.v1"
                if family in _ROLE_FAMILIES
                else "mixed_control"
            )
            for family in _CONTROL_FAMILIES
        },
    }
    controller = TextAbstractionController(
        programs=programs,
        regimes=_CONTROL_FAMILIES,
        evaluator=_evaluate_program,
        state_magic=STATE_MAGIC,
        grammar_id="general-task-byte-role-v1",
    )
    curriculum = {
        "schema": RESULT_SCHEMA,
        "candidate_space": candidate_space,
        "families": list(_CONTROL_FAMILIES),
        "supported_families": list(_SUPPORTED_FAMILIES),
        "transfer_tasks": {
            name: list(families) for name, families in _TRANSFER_TASKS.items()
        },
        "holdout_source": selected_holdout_source,
        "training_payloads": sorted(
            episode.payload_sha256 for episode in source_disjoint_training
        ),
        "holdout_payloads": sorted(
            episode.payload_sha256 for episode in source_disjoint_holdout
        ),
        "programs": [
            {
                "namespace": program.namespace,
                "sha256": program.sha256,
                "tokens": list(program.decoded),
            }
            for program in programs
        ],
    }
    curriculum_sha256 = _sha256(_canonical_bytes(curriculum))

    with TemporaryDirectory(prefix="cassi-general-task-gauntlet-") as directory:
        journal = QiIngressJournal(Path(directory) / "ingress", max_bytes=16 * 1024 * 1024)
        training_observations = _ingest_observations(
            journal,
            source_disjoint_training,
            split="training",
            profile_sha256=curriculum_sha256,
        )
        holdout_observations = _ingest_observations(
            journal,
            source_disjoint_holdout,
            split="holdout",
            profile_sha256=curriculum_sha256,
        )
        training_tasks = _task_episodes(
            training_observations,
            source_disjoint_training,
            controls,
        )
        holdout_tasks = _task_episodes(
            holdout_observations,
            source_disjoint_holdout,
            controls,
        )

        initial_state = controller.new_state()
        if initial_state.field.device.type != "cpu":
            raise QiFieldError("general-task gauntlet must run on CPU")
        baseline = {
            family: asdict(_evaluate_family(controller, initial_state, family, rows))
            for family, rows in holdout_tasks.items()
        }
        if any(receipt["status"] != "exhausted" for receipt in baseline.values()):
            raise QiFieldError("untrained general-task field settled")

        state = initial_state
        trained_families: list[str] = []
        retention_steps = []
        family_receipts: dict[str, dict[str, Any]] = {}
        for family in _SUPPORTED_FAMILIES:
            untouched_before = {
                other: controller.regime_sha256(state, other)
                for other in _CONTROL_FAMILIES
                if other != family
            }
            state = controller.learn_regime(
                state,
                family,
                _training_examples(training_tasks[family], selected_holdout_source),
            )
            untouched_after = {
                other: controller.regime_sha256(state, other)
                for other in untouched_before
            }
            if untouched_after != untouched_before:
                raise QiFieldError("general-task update changed another field namespace")
            trained_families.append(family)
            receipt = _evaluate_family(
                controller,
                state,
                family,
                holdout_tasks[family],
            )
            if receipt.status != "selected" or receipt.exact != receipt.total:
                raise QiFieldError(f"general-task family did not transfer: {family}")
            family_receipts[family] = asdict(receipt)
            retained = {
                previous: asdict(
                    _evaluate_family(
                        controller,
                        state,
                        previous,
                        holdout_tasks[previous],
                    )
                )
                for previous in trained_families
            }
            if any(
                row["status"] != "selected" or row["exact"] != row["total"]
                for row in retained.values()
            ):
                raise QiFieldError("general-task curriculum forgot an earlier family")
            retention_steps.append(
                {
                    "after_family": family,
                    "retained": len(retained),
                    "minimum_accuracy": min(
                        row["accuracy"] for row in retained.values()
                    ),
                }
            )

        state = controller.learn_regime(
            state,
            "natural",
            _training_examples(training_tasks["natural"], selected_holdout_source),
        )
        natural = _evaluate_family(
            controller,
            state,
            "natural",
            holdout_tasks["natural"],
        )
        if natural.status != "exhausted":
            raise QiFieldError("general-task natural-language control falsely settled")

        state = controller.learn_regime(
            state,
            "ambiguous_case",
            _training_examples(
                training_tasks["ambiguous_case"],
                selected_holdout_source,
            ),
        )
        ambiguity = _evaluate_family(
            controller,
            state,
            "ambiguous_case",
            holdout_tasks["ambiguous_case"],
        )
        if ambiguity.status != "ambiguous":
            raise QiFieldError("general-task ambiguity control did not remain ambiguous")

        retained_after_controls = {
            family: asdict(
                _evaluate_family(controller, state, family, holdout_tasks[family])
            )
            for family in _SUPPORTED_FAMILIES
        }
        if any(
            row["status"] != "selected" or row["exact"] != row["total"]
            for row in retained_after_controls.values()
        ):
            raise QiFieldError("general-task controls interfered with learned families")

        transfer = _composition_receipts(
            controller,
            state,
            holdout_tasks,
            controls,
        )
        if any(row["exact"] != row["total"] for row in transfer.values()):
            raise QiFieldError("general-task composition transfer failed")

        codec_invariance: dict[str, dict[str, int | float]] = {}
        for family in _SUPPORTED_FAMILIES:
            program = controller.selected_program(state, family)
            if program is None:
                raise QiFieldError("general-task selected program disappeared")
            for episode in holdout_tasks[family]:
                row = codec_invariance.setdefault(
                    episode.codec_id,
                    {"exact": 0, "total": 0, "accuracy": 0.0},
                )
                row["total"] = int(row["total"]) + 1
                row["exact"] = int(row["exact"]) + int(
                    _evaluate_program(program, episode.prompt, len(episode.target))
                    == episode.target
                )
        for row in codec_invariance.values():
            row["accuracy"] = int(row["exact"]) / int(row["total"])
        if any(row["exact"] != row["total"] for row in codec_invariance.values()):
            raise QiFieldError("general-task codec round-trip changed task input")

        shuffled_examples = list(
            _training_examples(training_tasks["ascii_upper"], selected_holdout_source)
        )
        shuffled_targets = [target for _, target in shuffled_examples]
        shuffled_targets = shuffled_targets[1:] + shuffled_targets[:1]
        shuffled_state = controller.learn_regime(
            controller.new_state(),
            "ascii_upper",
            tuple(
                (prompt, target)
                for (prompt, _), target in zip(
                    shuffled_examples,
                    shuffled_targets,
                    strict=True,
                )
            ),
        )
        shuffled_selection = controller.select(shuffled_state, "ascii_upper")
        if shuffled_selection.status != "exhausted":
            raise QiFieldError("shuffled-outcome control falsely settled")

        lesion_family = "suffix4"
        lesioned_state = state
        eligible_program_ids = tuple(
            record.program_id
            for record in controller.records(state, lesion_family)
            if record.evidence.eligible
        )
        for program_id in eligible_program_ids:
            lesioned_state = controller.clear_program(
                lesioned_state,
                lesion_family,
                program_id,
            )
        lesioned_selection = controller.select(lesioned_state, lesion_family)
        if lesioned_selection.status != "exhausted":
            raise QiFieldError("field lesion did not remove the learned result")
        lesion_control = _evaluate_family(
            controller,
            lesioned_state,
            "ascii_upper",
            holdout_tasks["ascii_upper"],
        )
        if lesion_control.status != "selected" or lesion_control.exact != lesion_control.total:
            raise QiFieldError("field lesion changed an unrelated family")

        checkpoint = controller.dump_state_bytes(state)
        restored = controller.load_state_bytes(checkpoint)
        if (
            controller.state_sha256(restored) != controller.state_sha256(state)
            or controller.dump_state_bytes(restored) != checkpoint
        ):
            raise QiFieldError("general-task checkpoint did not reload exactly")

        inference_sha256 = controller.state_sha256(restored)
        for family in _CONTROL_FAMILIES:
            _evaluate_family(controller, restored, family, holdout_tasks[family])
        if controller.state_sha256(restored) != inference_sha256:
            raise QiFieldError("general-task inference changed the trained field")

        horizon_state = restored
        max_abs = float(horizon_state.field.abs().max().item())
        for update in range(long_horizon_updates):
            family = _SUPPORTED_FAMILIES[update % len(_SUPPORTED_FAMILIES)]
            horizon_state = controller.learn_regime(
                horizon_state,
                family,
                _training_examples(training_tasks[family], selected_holdout_source),
            )
            if not bool(horizon_state.field.isfinite().all().item()):
                raise QiFieldError("general-task long-horizon field became nonfinite")
            max_abs = max(max_abs, float(horizon_state.field.abs().max().item()))
        if controller.state_sha256(horizon_state) != inference_sha256:
            raise QiFieldError("general-task long-horizon fixed point drifted")

        malformed = _append_malformed_control(journal, curriculum_sha256)
        journal_head = journal.head_sha256
        references = journal.replay()
        reopened = QiIngressJournal(
            Path(directory) / "ingress",
            max_bytes=16 * 1024 * 1024,
        )
        replayed = reopened.replay()
        if replayed != references or reopened.head_sha256 != journal_head:
            raise QiFieldError("general-task ingress replay changed across restart")
        for reference in replayed:
            reopened.read_packet(reference)

        result = {
            "schema": RESULT_SCHEMA,
            "curriculum_sha256": curriculum_sha256,
            "candidate_space": candidate_space,
            "corpus": {
                "training_receipt_episodes": len(training),
                "holdout_receipt_episodes": len(holdout),
                "training_episodes": len(source_disjoint_training),
                "holdout_episodes": len(source_disjoint_holdout),
                "holdout_source": selected_holdout_source,
                "split_strategy": "leave_one_source_out",
                "raw_receipt_source_overlap": sorted(
                    {episode.source_id for episode in training}
                    & {episode.source_id for episode in holdout}
                ),
                "selected_split_source_overlap": sorted(
                    {episode.source_id for episode in source_disjoint_training}
                    & {episode.source_id for episode in source_disjoint_holdout}
                ),
                "source_disjoint": True,
                "episode_disjoint": True,
                "training_payload_sha256": _sha256(
                    _canonical_bytes(
                        sorted(
                            episode.payload_sha256
                            for episode in source_disjoint_training
                        )
                    )
                ),
                "holdout_payload_sha256": _sha256(
                    _canonical_bytes(
                        sorted(
                            episode.payload_sha256
                            for episode in source_disjoint_holdout
                        )
                    )
                ),
            },
            "field": {
                "shape": list(state.field.shape),
                "dtype": str(state.field.dtype),
                "device": state.field.device.type,
                "checkpoint_sha256": _sha256(checkpoint),
                "state_sha256": inference_sha256,
                "checkpoint_reload_exact": True,
                "inference_preserved_state": True,
                "sequential_updates": len(_SUPPORTED_FAMILIES) + 2,
                "long_horizon_updates": long_horizon_updates,
                "long_horizon_max_abs": max_abs,
                "long_horizon_fixed_point": True,
            },
            "baseline": baseline,
            "families": family_receipts,
            "retention": {
                "steps": retention_steps,
                "retained_after_controls": retained_after_controls,
                "minimum_accuracy": min(
                    row["accuracy"] for row in retained_after_controls.values()
                ),
                "maximum_accuracy_drop": 0.0,
            },
            "transfer": {
                "cross_task_composition": transfer,
                "codec_invariance": codec_invariance,
                "learned_cross_view": {
                    "status": "unsupported",
                    "reason": "fixed_projection_only",
                },
            },
            "controls": {
                "natural": asdict(natural),
                "ambiguous": {
                    **asdict(ambiguity),
                    "selection": _selection_payload(
                        controller.select(state, "ambiguous_case")
                    ),
                },
                "unsupported": malformed,
                "shuffled_outcomes": _selection_payload(shuffled_selection),
                "field_lesion": {
                    "family": lesion_family,
                    "cleared_program_ids": list(eligible_program_ids),
                    "selection_after": _selection_payload(lesioned_selection),
                    "unrelated_family_accuracy": lesion_control.accuracy,
                },
            },
            "ingress": {
                "entries": len(references),
                "head_sha256": journal_head,
                "restart_replay_exact": True,
                "training_codecs": sorted(
                    {observation.codec_id for observation in training_observations}
                ),
                "holdout_codecs": sorted(
                    {observation.codec_id for observation in holdout_observations}
                ),
            },
            "readiness": {
                "status": "not_ready",
                "missing": ["learned_cross_view_transfer"],
            },
            "diagnostic_checks_passed": True,
            "readiness_validated": False,
        }
        return result


def run_general_task_gauntlet(
    training: Sequence[TaskCorpusEpisode] | None = None,
    holdout: Sequence[TaskCorpusEpisode] | None = None,
    *,
    holdout_source: str | None = None,
    long_horizon_updates: int = 256,
) -> dict[str, Any]:
    use_default_corpus = training is None and holdout is None
    with _FieldOnlyRuntimeAudit() as audit:
        reproduction = (
            _reproduce_existing_entrypoints()
            if use_default_corpus
            else {"status": "not_run", "reason": "custom_corpus"}
        )
        result = _run_general_task_gauntlet(
            training,
            holdout,
            holdout_source=holdout_source,
            long_horizon_updates=long_horizon_updates,
        )
        result["reproduction"] = reproduction
        if use_default_corpus:
            result["diagnostic_checks_passed"] = bool(
                result["diagnostic_checks_passed"]
                and reproduction["diagnostic_checks_passed"]
            )
    if result["field"]["device"] != "cpu":
        raise QiFieldError("general-task gauntlet left the CPU execution path")
    result["field_only"] = audit.receipt()
    return result


def run_gauntlet_phase(phase: str) -> dict[str, Any]:
    phase_fields = {
        "curriculum": ("candidate_space", "corpus", "baseline", "families"),
        "holdouts": ("corpus", "families", "transfer"),
        "retention": ("corpus", "retention"),
        "persistence": ("field", "ingress"),
        "controls": ("controls", "readiness"),
    }
    if phase == "full":
        return run_general_task_gauntlet()
    if phase == "reproduction":
        with _FieldOnlyRuntimeAudit() as audit:
            reproduction = _reproduce_existing_entrypoints()
        return {
            "schema": RESULT_SCHEMA,
            "phase": phase,
            "execution_scope": "reproduction_only",
            "reproduction": reproduction,
            "field_only": audit.receipt(),
            "diagnostic_checks_passed": reproduction[
                "diagnostic_checks_passed"
            ],
            "readiness_validated": False,
        }
    try:
        fields = phase_fields[phase]
    except KeyError as error:
        raise QiFieldError(f"unknown general-task gauntlet phase: {phase}") from error
    with _FieldOnlyRuntimeAudit() as audit:
        complete = _run_general_task_gauntlet()
    return {
        "schema": RESULT_SCHEMA,
        "phase": phase,
        "execution_scope": "full_prerequisite_chain",
        "metrics": {field: complete[field] for field in fields},
        "field_only": audit.receipt(),
        "diagnostic_checks_passed": complete["diagnostic_checks_passed"],
        "readiness_validated": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the CPU-only bounded Field Intelligence training gauntlet."
    )
    parser.add_argument(
        "--phase",
        choices=(
            "reproduction",
            "curriculum",
            "holdouts",
            "retention",
            "persistence",
            "controls",
            "full",
        ),
        default="full",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="return exit code 2 unless the receipt validates readiness",
    )
    return parser


def _persist_receipt(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = run_gauntlet_phase(arguments.phase)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    _persist_receipt(arguments.output, payload)
    print(payload, end="")
    if not result["diagnostic_checks_passed"]:
        return 1
    if arguments.require_ready and not result["readiness_validated"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
