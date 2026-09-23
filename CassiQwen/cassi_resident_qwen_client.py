"""Field-owned resident Qwen client.

This adapter deliberately contains no model loop.  It turns a chat request into
one digest-bound model graph task owned by the entity's existing
:class:`ProgrammableSwarm`; the swarm advances the graph and services each
``resident-model-stage`` wait through ``ResidentQwenExecutor``.  The executor
is numerical/mechanical only, while task state and learned policy remain in the
field owner.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # A field-owned resource wait is not a missing brain.
    from cassi_field_regions import ResidencyWait as _RegionalResidencyWait
    from cassi_field_residency import ResourceWait as _ResourceWait
    from cassi_learning_computer import (
        LearningComputerResidencyWait as _ComputerResidencyWait,
    )
except ImportError:  # pragma: no cover - the field modules share the process
    _FieldResourceWait: tuple[type[BaseException], ...] = ()
else:
    # The condition can arrive as the manager's wait, a regional
    # paged-structure wait, or the computer's typed residency continuation;
    # none of them means the brain is missing.
    _FieldResourceWait = (
        _ResourceWait,
        _RegionalResidencyWait,
        _ComputerResidencyWait,
    )


try:
    from programs.model.gguf import build_gguf_model_package, inspect_gguf
except Exception as exc:  # pragma: no cover - clear error is raised on use
    build_gguf_model_package = None  # type: ignore[assignment]
    inspect_gguf = None  # type: ignore[assignment]
    _MODEL_IMPORT_ERROR = exc
else:
    _MODEL_IMPORT_ERROR = None
from surface.visual_adapter import (
    unsupported_visual_capability,
    unsupported_visual_result,
)






DEFAULT_MODEL_NAME = "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf"
CLIENT_SCHEMA = "cassi.resident-qwen-client.v1"

RESIDENT_PREFIX_REUSE_SCHEMA = "cassifi.resident-qwen-prefix-reuse.v1"
MAX_RESIDENT_PREFIX_CONVERSATIONS = 32


class ResidentQwenUnavailable(RuntimeError):
    """The explicitly selected resident brain cannot execute a request."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()




def _plain(value: Any) -> Any:
    return json.loads(_canonical(value).decode("utf-8"))


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResidentQwenUnavailable(f"{label} must be an object")
    return value


class ResidentQwenClient:
    """Chat-shaped adapter over one owner-backed resident Qwen graph.

    Construction verifies the immutable GGUF identity and metadata only.  No
    llama context, HTTP service, or model weights are launched.  ``bind_entity``
    attaches the executor to the entity's already-created swarm member; normal
    completion then submits a graph task and lets that swarm service one stage
    at a time.
    """

    def __init__(
        self,
        model_path: str | Path,
        state_directory: str | Path,
        *,
        backend: str = "cpu",
        library_path: str | Path | None = None,
        threads: int = 8,
    ) -> None:
        self.model_path = Path(model_path).resolve()
        self.state_directory = Path(state_directory).resolve()
        self.backend = str(backend).lower()
        self.library_path = None if library_path is None else Path(library_path).resolve()
        self.threads = threads
        if self.backend not in {"cpu", "vulkan"}:
            raise ValueError("resident backend must be cpu or vulkan")
        if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
            raise ValueError("resident threads must be a positive integer")
        if not self.model_path.is_file():
            raise FileNotFoundError(self.model_path)
        self.model_id = self.model_path.name
        self.model_metadata: Mapping[str, Any] = {}
        if inspect_gguf is None:
            raise ResidentQwenUnavailable(
                f"GGUF importer is unavailable: {_MODEL_IMPORT_ERROR}"
            )
        try:
            manifest = inspect_gguf(self.model_path, source_id=self.model_path.name)
        except Exception as exc:
            raise ResidentQwenUnavailable(f"cannot inspect resident GGUF: {exc}") from exc
        self._manifest = manifest
        source_sha256 = manifest.get("source_sha256")
        if not isinstance(source_sha256, str) or len(source_sha256) != 64:
            raise ResidentQwenUnavailable("resident GGUF importer returned no source identity")
        self.model_sha256 = source_sha256
        metadata = manifest.get("model_metadata", manifest.get("metadata"))
        if isinstance(metadata, Mapping):
            self.model_metadata = dict(metadata)
        self.source_id = str(manifest.get("source_id", self.model_path.name))
        self.architecture = str(self.model_metadata.get("general.architecture", ""))
        if not self.architecture:
            raise ResidentQwenUnavailable("resident GGUF has no general.architecture")
        self._executor: Any | None = None
        self._package_cache: Any | None = None
        self._context_length = next(
            (
                int(value)
                for key, value in self.model_metadata.items()
                if str(key).endswith(".context_length")
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value > 0
            ),
            int(self.model_metadata.get("context_length", 32_768)),
        )
        self._tokenizer: Any | None = None
        self._swarm: Any | None = None
        self._member_id: str | None = None
        self._program_id = "resident-qwen"
        self._closed = False
        self._resident_prefix_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._latest_resident_prefix: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        self._visual_client: Any | None = None
    def _ensure_executor(self) -> Any:
        if self._closed:
            raise ResidentQwenUnavailable("resident Qwen client is closed")
        if self._executor is None:
            try:
                from programs.model.qwen_executor import ResidentQwenExecutor
            except Exception as exc:
                raise ResidentQwenUnavailable(
                    f"resident Qwen executor is unavailable: {exc}"
                ) from exc
            try:
                self._executor = ResidentQwenExecutor(
                    self.model_path,
                    self.state_directory,
                    backend=self.backend,
                    library_path=self.library_path,
                    threads=self.threads,
                    manifest=self._manifest,
                )
            except Exception as exc:
                raise ResidentQwenUnavailable(
                    f"resident Qwen executor could not open model: {exc}"
                ) from exc
        return self._executor
    def _ensure_tokenizer(self) -> Any:
        if self._closed:
            raise ResidentQwenUnavailable("resident Qwen client is closed")
        if self._tokenizer is None:
            try:
                from programs.model.tokenizer import GGUFTokenizer
                self._tokenizer = GGUFTokenizer(self.model_path)
            except Exception as exc:
                raise ResidentQwenUnavailable(
                    f"resident tokenizer is unavailable: {exc}"
                ) from exc
        return self._tokenizer

    def visual_capabilities(self) -> Mapping[str, Any]:
        """Report an optional local vision instrument separate from the resident text graph."""
        if self._visual_client is not None:
            capability = dict(self._visual_client.visual_capabilities())
            capability["resident_brain"] = {
                "model_id": self.model_id,
                "model_sha256": self.model_sha256,
                "architecture": self.architecture,
                "runtime_id": "ResidentQwenExecutor",
                "role": "field-owned-text-brain",
            }
            capability["vision_instrument"] = "separate-loopback-llama.cpp"
            return capability
        return unsupported_visual_capability(
            model_id=self.model_id,
            model_sha256=self.model_sha256,
            architecture=self.architecture,
            runtime_id="ResidentQwenExecutor",
            input_transport="field-owned text-token graph",
            reason_code="resident_executor_text_only",
            reason=(
                "The resident executor accepts prompt token IDs only. No separate "
                "loopback multimodal instrument is configured, so no pixel pages "
                "are read or forwarded and text-only fallback is disabled."
            ),
            model_capability="unverified",
        )

    def complete_visual(
        self,
        *,
        prompt: str,
        image_pages: Sequence[Mapping[str, Any]],
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Use the explicitly configured loopback vision instrument, never text-tokenize images."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty text")
        if isinstance(image_pages, (str, bytes)) or not isinstance(
            image_pages, Sequence
        ):
            raise TypeError("image_pages must be a sequence of field page references")
        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 4096
        ):
            raise ValueError("max_tokens must be between 1 and 4096")
        if self._visual_client is None:
            return unsupported_visual_result(
                self.visual_capabilities(), requested_frames=len(image_pages)
            )
        return self._visual_client.complete_visual(
            prompt=prompt,
            image_pages=image_pages,
            max_tokens=max_tokens,
            thinking=thinking,
            response_format=response_format,
        )




    def bind_entity(self, entity: Any) -> Mapping[str, Any]:
        """Bind to the entity's existing owner/member; never create an owner.

        Executor construction is intentionally deferred until the first model
        request.  Binding the field lane itself is metadata-only and therefore
        safe during service startup.
        """
        if self._closed:
            raise ResidentQwenUnavailable("resident Qwen client is closed")
        swarm = getattr(entity, "program_runtime", None)
        member_id = getattr(entity, "_program_member_id", None)
        if swarm is None or not isinstance(member_id, str) or not member_id:
            raise ResidentQwenUnavailable(
                "entity has no owner-backed programmable field for resident Qwen"
            )
        self._swarm = swarm
        self._member_id = member_id
        return {
            "schema": CLIENT_SCHEMA,
            "status": "ready",
            "model_id": self.model_id,
            "source_sha256": self.model_sha256,
            "backend": self.backend,
            "loaded": False,
        }
    def tokenize(self, text: str, add_special: bool = False) -> list[int]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        tokenizer = self._ensure_tokenizer()
        try:
            values = tokenizer.encode(text, add_special=bool(add_special))
        except Exception as exc:
            raise ResidentQwenUnavailable(f"resident tokenizer failed: {exc}") from exc
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise ResidentQwenUnavailable("resident tokenizer returned no token sequence")
        tokens = [int(value) for value in values]
        if any(value < 0 for value in tokens):
            raise ResidentQwenUnavailable("resident tokenizer returned an invalid token")
        return tokens

    def detokenize(self, tokens: Sequence[int]) -> str:
        if isinstance(tokens, (str, bytes)):
            raise TypeError("tokens must be a sequence of integers")
        tokenizer = self._ensure_tokenizer()
        try:
            result = tokenizer.decode([int(value) for value in tokens])
        except Exception as exc:
            raise ResidentQwenUnavailable(f"resident detokenizer failed: {exc}") from exc
        if not isinstance(result, str):
            raise ResidentQwenUnavailable("resident detokenizer returned non-text output")
        return result

    @staticmethod
    def _chat_prompt(prompt: str, *, thinking: bool, response_format: Mapping[str, Any] | None) -> str:
        instruction = "Deliver the requested JSON answer."
        if response_format is not None:
            instruction += " Return an object matching this response schema: " + json.dumps(
                dict(response_format), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        if thinking:
            instruction += " Think privately, then provide only the final answer."
        return (
            "<|im_start|>system\n" + instruction + "<|im_end|>\n"
            "<|im_start|>user\n" + prompt + "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    def count_completion_input_tokens(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> int:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty text")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        return len(self.tokenize(self._chat_prompt(prompt, thinking=thinking, response_format=response_format)))

    def context(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
        context_tokens: int | None = None,
    ) -> Mapping[str, Any]:
        input_tokens = self.count_completion_input_tokens(
            prompt=prompt,
            max_tokens=max_tokens,
            thinking=thinking,
            response_format=response_format,
        )
        capacity = int(context_tokens or self._context_length)
        available = capacity - input_tokens - int(max_tokens)
        return {
            "schema": "cassi.resident-qwen-context.v1",
            "input_tokens": input_tokens,
            "completion_tokens": int(max_tokens),
            "context_tokens": capacity,
            "available_tokens": available,
            "fits": available >= 0,
            "model_sha256": self.model_sha256,
        }

    def _package(self) -> Any:
        if self._package_cache is not None:
            return self._package_cache
        if build_gguf_model_package is None:
            raise ResidentQwenUnavailable("GGUF model package builder is unavailable")
        try:
            self._package_cache = build_gguf_model_package(
                self.model_path,
                program_id=self._program_id,
                owner_id=f"resident-qwen:{self.model_sha256}",
                manifest=self._manifest,
                source_id=self.source_id,
                expected_source_sha256=self.model_sha256,
            )
        except Exception as exc:
            raise ResidentQwenUnavailable(f"resident model graph import failed: {exc}") from exc
        return self._package_cache

    @staticmethod
    def _split_reasoning(text: str) -> tuple[str, str]:
        matches = re.findall(r"<think>(.*?)</think>", text, flags=re.IGNORECASE | re.DOTALL)
        reasoning = "\n".join(match.strip() for match in matches if match.strip())
        content = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        return content, reasoning

    def _release_field_task(self, task_id: str, *, strict: bool) -> Mapping[str, Any] | None:
        """Reclaim the field program task of one completion attempt.

        The runtime holds a bounded task region, so each finished or faulted
        continuation is released instead of accumulating one task per request.
        """

        assert self._swarm is not None and self._member_id is not None
        try:
            return self._swarm.release_task(self._member_id, task_id)
        except _FieldResourceWait:
            if not strict:
                # A failing attempt keeps its own error: a deferred reclaim must
                # not replace the failure the caller is about to see.
                return None
            # Physical room, not capability: the finished task stays durable in
            # its own state, and the same request identity reclaims it on the
            # retry rather than reporting a working brain as unavailable.
            raise
        except Exception as exc:
            if strict:
                raise ResidentQwenUnavailable(
                    f"resident model task release failed: {exc}"
                ) from exc
            # A failing attempt keeps its own error; the unclaimed task then
            # surfaces as a precise capacity fault on the next request.
            return None

    def _task_result(
        self, task_id: str
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        assert self._swarm is not None and self._member_id is not None
        view = _mapping(self._swarm.inspect(self._member_id, task_id=task_id), "resident model view")
        status = str(view.get("status", ""))
        if status != "completed":
            error = view.get("result") or view.get("unfinished_reason") or status
            raise ResidentQwenUnavailable(f"resident model task did not complete: {error}")
        result = view.get("result")
        if not isinstance(result, Mapping):
            raise ResidentQwenUnavailable("resident model task returned no result")
        return result, view

    def _resident_field_epoch(self) -> str | None:
        if self._swarm is None or self._member_id is None:
            return None
        getter = getattr(self._swarm, "resident_field_state_sha256", None)
        if not callable(getter):
            return None
        try:
            value = getter(self._member_id)
        except _FieldResourceWait:
            raise
        except Exception:
            return None
        value = str(value)
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            return None
        return value

    def advance_resident_prefix_epoch(
        self,
        conversation_id: str,
        *,
        expected_epoch_sha256: str,
        next_epoch_sha256: str,
    ) -> bool:
        """Allow only an explicit same-conversation field transition."""
        if (
            not isinstance(conversation_id, str)
            or not conversation_id
            or not isinstance(expected_epoch_sha256, str)
            or not isinstance(next_epoch_sha256, str)
            or len(expected_epoch_sha256) != 64
            or len(next_epoch_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_epoch_sha256)
            or any(character not in "0123456789abcdef" for character in next_epoch_sha256)
            or self._member_id is None
        ):
            return False
        base_key = (
            self.model_sha256,
            self.backend,
            self._member_id,
            conversation_id,
        )
        cache_key = self._latest_resident_prefix.get(base_key)
        entry = self._resident_prefix_cache.get(cache_key) if cache_key is not None else None
        if not isinstance(entry, dict) or entry.get("field_epoch_sha256") != expected_epoch_sha256:
            return False
        entry["field_epoch_sha256"] = next_epoch_sha256
        return True

    def _resident_prefix_candidate(
        self,
        prompt_tokens: Sequence[int],
        conversation_id: str | None,
        executor: Any,
    ) -> tuple[Mapping[str, Any] | None, str]:
        if not conversation_id:
            return None, "conversation-identity-required"
        if self._swarm is None or self._member_id is None:
            return None, "field-not-bound"
        base_key = (
            self.model_sha256,
            self.backend,
            self._member_id,
            conversation_id,
        )
        cache_key = self._latest_resident_prefix.get(base_key)
        entry = self._resident_prefix_cache.get(cache_key) if cache_key is not None else None
        if not isinstance(entry, Mapping):
            return None, "no-cached-prefix"
        try:
            current_epoch = self._resident_field_epoch()
        except _FieldResourceWait:
            return None, "field-epoch-unavailable"
        if current_epoch is None:
            return None, "field-epoch-unavailable"
        if current_epoch != entry.get("field_epoch_sha256"):
            self._resident_prefix_cache.pop(cache_key, None)
            self._latest_resident_prefix.pop(base_key, None)
            return None, "field-epoch-mismatch"
        old_tokens = entry.get("tokens")
        if not isinstance(old_tokens, tuple):
            return None, "cached-prefix-invalid"
        common_length = 0
        limit = min(len(old_tokens), len(prompt_tokens))
        while common_length < limit and old_tokens[common_length] == prompt_tokens[common_length]:
            common_length += 1
        boundaries = entry.get("boundaries")
        if not isinstance(boundaries, Sequence) or isinstance(boundaries, (str, bytes)):
            return None, "cached-prefix-invalid"
        loader = getattr(executor, "_load_state", None)
        if not callable(loader):
            return None, "snapshot-loader-unavailable"
        graph = self._package().graph
        if len(graph) < 2 or graph[-1].get("op") != "qwen-head":
            return None, "unsupported-prefix-graph"
        terminal = graph[-2]
        terminal_layer = terminal.get("parameters", {}).get("layer")
        for boundary in reversed(boundaries):
            if not isinstance(boundary, Mapping) or boundary.get("head_executed") is not False:
                continue
            position = boundary.get("position")
            token = boundary.get("token")
            snapshot = boundary.get("snapshot")
            if (
                isinstance(position, bool)
                or not isinstance(position, int)
                or position < 0
                or position >= common_length
                or position >= len(old_tokens)
                or position >= len(prompt_tokens)
                or isinstance(token, bool)
                or not isinstance(token, int)
                or token != old_tokens[position]
                or token != prompt_tokens[position]
                or not isinstance(snapshot, Mapping)
            ):
                continue
            try:
                _, metadata = loader({"snapshot": dict(snapshot)})
            except Exception:
                continue
            if (
                not isinstance(metadata, Mapping)
                or metadata.get("source_sha256") != self.model_sha256
                or metadata.get("architecture") != self.architecture
                or metadata.get("position") != position
                or metadata.get("token") != token
                or metadata.get("stage") != terminal.get("stage")
                or metadata.get("layer") != terminal_layer
                or metadata.get("backend") != self.backend
            ):
                continue
            prefix_tokens = [int(value) for value in prompt_tokens[: position + 1]]
            return {
                "schema": RESIDENT_PREFIX_REUSE_SCHEMA,
                "conversation_id": conversation_id,
                "source_sha256": self.model_sha256,
                "backend": self.backend,
                "field_epoch_sha256": current_epoch,
                "prefix_token_count": position + 1,
                "prefix_sha256": _sha256_bytes(_canonical(prefix_tokens)),
                "position": position,
                "token": int(prompt_tokens[position]),
                "head_executed": False,
                "snapshot": _plain(dict(snapshot)),
            }, "eligible-prefix"
        return None, "no-matching-stage-boundary"

    def _record_resident_prefix(
        self,
        *,
        prompt_tokens: Sequence[int],
        conversation_id: str | None,
        view: Mapping[str, Any],
        field_epoch_sha256: str | None,
        seed: Mapping[str, Any] | None,
    ) -> None:
        if (
            not conversation_id
            or self._member_id is None
            or field_epoch_sha256 is None
            or len(field_epoch_sha256) != 64
        ):
            return
        resident = view.get("resident_model")
        if not isinstance(resident, Mapping):
            return
        captured = resident.get("prefix_snapshots")
        if not isinstance(captured, Sequence) or isinstance(captured, (str, bytes)):
            return
        boundaries: dict[int, dict[str, Any]] = {}
        for item in captured:
            if not isinstance(item, Mapping):
                continue
            position = item.get("position")
            token = item.get("token")
            snapshot = item.get("snapshot")
            head_executed = item.get("head_executed")
            if (
                isinstance(position, bool)
                or not isinstance(position, int)
                or not 0 <= position < len(prompt_tokens)
                or isinstance(token, bool)
                or not isinstance(token, int)
                or token != int(prompt_tokens[position])
                or not isinstance(head_executed, bool)
                or not isinstance(snapshot, Mapping)
            ):
                continue
            boundaries[position] = {
                "position": position,
                "token": token,
                "head_executed": head_executed,
                "snapshot": _plain(dict(snapshot)),
            }
        base_key = (
            self.model_sha256,
            self.backend,
            self._member_id,
            conversation_id,
        )
        old_key = self._latest_resident_prefix.get(base_key)
        old_entry = self._resident_prefix_cache.get(old_key) if old_key is not None else None
        if seed is not None and isinstance(old_entry, Mapping):
            old_tokens = old_entry.get("tokens")
            seed_count = seed.get("prefix_token_count")
            if (
                isinstance(old_tokens, tuple)
                and isinstance(seed_count, int)
                and not isinstance(seed_count, bool)
                and len(prompt_tokens) >= seed_count
                and tuple(int(value) for value in prompt_tokens[:seed_count])
                == old_tokens[:seed_count]
            ):
                old_boundaries = old_entry.get("boundaries", ())
                if isinstance(old_boundaries, Sequence):
                    for item in old_boundaries:
                        if (
                            isinstance(item, Mapping)
                            and isinstance(item.get("position"), int)
                            and not isinstance(item.get("position"), bool)
                            and int(item["position"]) < seed_count
                        ):
                            boundaries.setdefault(int(item["position"]), _plain(dict(item)))
        if not boundaries:
            return
        tokens = tuple(int(value) for value in prompt_tokens)
        cache_key = (*base_key, tokens)
        if old_key is not None and old_key != cache_key:
            self._resident_prefix_cache.pop(old_key, None)
        self._latest_resident_prefix.pop(base_key, None)
        self._resident_prefix_cache[cache_key] = {
            "tokens": tokens,
            "field_epoch_sha256": field_epoch_sha256,
            "boundaries": [boundaries[position] for position in sorted(boundaries)],
        }
        self._latest_resident_prefix[base_key] = cache_key
        while len(self._latest_resident_prefix) > MAX_RESIDENT_PREFIX_CONVERSATIONS:
            oldest_base_key = next(iter(self._latest_resident_prefix))
            oldest_cache_key = self._latest_resident_prefix.pop(oldest_base_key)
            self._resident_prefix_cache.pop(oldest_cache_key, None)

    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> Mapping[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty text")
        if conversation_id is not None and (
            not isinstance(conversation_id, str) or not conversation_id.strip()
        ):
            raise ValueError("conversation_id must be nonempty text when supplied")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 65_536:
            raise ValueError("max_tokens must be an integer in 1..65536")
        if self._swarm is None or self._member_id is None:
            raise ResidentQwenUnavailable("resident Qwen is not bound to the entity field")
        executor = self._ensure_executor()
        text = self._chat_prompt(prompt, thinking=thinking, response_format=response_format)
        prompt_tokens = self.tokenize(text)
        tokenizer = self._ensure_tokenizer()
        stop_tokens = tuple(sorted(int(value) for value in getattr(tokenizer, "eog_ids", ())))
        request_body = {
            "schema": CLIENT_SCHEMA,
            "model_sha256": self.model_sha256,
            "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
            "prompt_tokens": prompt_tokens,
            "max_tokens": max_tokens,
            "thinking": bool(thinking),
            "response_format": None if response_format is None else dict(response_format),
            "backend": self.backend,
            "conversation_id": conversation_id,
        }
        operation_id = _sha256_bytes(_canonical(request_body))
        task_id = f"resident-qwen:{operation_id[:48]}"
        package = self._package()
        started = time.perf_counter_ns()
        prefix_seed: Mapping[str, Any] | None = None
        prefix_reason = "not-attempted"
        try:
            try:
                self._swarm.bind_resident_model(self.model_sha256, executor)
            except _FieldResourceWait:
                # Physical room, not capability: the field keeps its place, so
                # the caller must be able to wait rather than read this as a
                # missing brain.
                raise
            except Exception as exc:
                raise ResidentQwenUnavailable(f"resident model binding failed: {exc}") from exc
            prefix_seed, prefix_reason = self._resident_prefix_candidate(
                prompt_tokens,
                conversation_id,
                executor,
            )
            try:
                self._swarm.start_model(
                    self._member_id,
                    package,
                    prompt_tokens=tuple(prompt_tokens),
                    max_new_tokens=max_tokens,
                    placement="logical-cpu",
                    stop_tokens=stop_tokens,
                    sampler={"mode": "greedy", "temperature": 0.0, "top_k": 0},
                    operation_id=operation_id,
                    task_id=task_id,
                    lineage_id=f"resident-qwen:{self.model_sha256}",
                    resident_prefix=prefix_seed,
                    steps=0,
                )
            except _FieldResourceWait:
                # The same wait can arrive while the start reserves its pages;
                # the idempotency fallback below must not read a deferred start
                # as an absent task and turn a wait into a fault.
                raise
            except Exception as exc:
                # A deterministic task identity makes retries idempotent.  If
                # the owner already has it, resume rather than creating a twin.
                try:
                    self._swarm.inspect(self._member_id, task_id=task_id)
                except Exception:
                    raise ResidentQwenUnavailable(
                        f"resident model task start failed: {exc}"
                    ) from exc
            graph = package.graph if hasattr(package, "graph") else package.get("graph", ())
            stage_groups = len(graph) * (len(prompt_tokens) + max_tokens + 1) + 32
            self._swarm.run_to_boundary(
                self._member_id,
                task_id=task_id,
                quantum=1,
                max_groups=max(1_024, stage_groups),
            )
            result, view = self._task_result(task_id)
        except _FieldResourceWait:
            # Physical room, not capability: the pending stage keeps its place.
            raise
        except Exception as exc:
            # Reclaim the task before reporting: a failed attempt would
            # otherwise keep its whole state resident in the bounded runtime
            # task region until that region is exhausted.
            self._release_field_task(task_id, strict=False)
            if isinstance(exc, ResidentQwenUnavailable):
                raise
            raise ResidentQwenUnavailable(f"resident model execution failed: {exc}") from exc
        self._release_field_task(task_id, strict=True)
        try:
            field_epoch_after = self._resident_field_epoch()
        except _FieldResourceWait:
            # Prefix caching is optional; a cache-index read must not defer a
            # completed model request.
            field_epoch_after = None
        resident_view = view.get("resident_model")
        reuse_metadata = (
            resident_view.get("prefix_reuse")
            if isinstance(resident_view, Mapping)
            else None
        )
        prefix_hit = (
            isinstance(reuse_metadata, Mapping)
            and reuse_metadata.get("schema") == RESIDENT_PREFIX_REUSE_SCHEMA
            and reuse_metadata.get("source_sha256") == self.model_sha256
            and reuse_metadata.get("backend") == self.backend
            and reuse_metadata.get("conversation_id") == conversation_id
        )
        reused_prefix_tokens = (
            int(reuse_metadata.get("prefix_token_count", 0)) if prefix_hit else 0
        )
        reused_stage_count = (
            int(reuse_metadata.get("reused_stage_count", 0)) if prefix_hit else 0
        )
        self._record_resident_prefix(
            prompt_tokens=prompt_tokens,
            conversation_id=conversation_id,
            view=view,
            field_epoch_sha256=field_epoch_after,
            seed=reuse_metadata if prefix_hit else None,
        )
        elapsed_ns = time.perf_counter_ns() - started
        generated = result.get("tokens", result.get("generated_tokens"))
        if not isinstance(generated, Sequence) or isinstance(generated, (str, bytes)):
            output = result.get("text", "")
            generated_tokens = []
        else:
            generated_tokens = [int(value) for value in generated]
            output = self.detokenize(generated_tokens)
        if not isinstance(output, str):
            raise ResidentQwenUnavailable("resident model result has no text output")
        content, reasoning = self._split_reasoning(output)
        if isinstance(result.get("reasoning_content"), str):
            reasoning = result["reasoning_content"]
        finish_reason = result.get("finish_reason") or (
            "length" if len(generated_tokens) >= max_tokens else "stop"
        )
        return {
            "content": content,
            "reasoning_content": reasoning,
            "thinking": bool(thinking),
            "finish_reason": finish_reason,
            "logprobs": result.get("logprobs"),
            "generation_parameters": {
                "max_tokens": max_tokens,
                "temperature": 0.0,
                "top_k": 0,
                "backend": self.backend,
            },
            "elapsed_ns": elapsed_ns,
            "usage": {
                "prompt_tokens": len(prompt_tokens),
                "completion_tokens": len(generated_tokens),
                "total_tokens": len(prompt_tokens) + len(generated_tokens),
            },
            "timings": result.get("timings", {}),
            "field_policies": result.get("field_policies"),
            "server_cassi_receipt": {
                "schema": CLIENT_SCHEMA,
                "executor": "cassi-resident-qwen",
                "source_sha256": self.model_sha256,
                "task_id": task_id,
                "operation_id": operation_id,
                "prefix_reuse": {
                    "schema": RESIDENT_PREFIX_REUSE_SCHEMA,
                    "hit": bool(prefix_hit),
                    "reason": (
                        "cache-hit"
                        if prefix_hit
                        and prefix_seed is not None
                        and reuse_metadata.get("prefix_sha256")
                        == prefix_seed.get("prefix_sha256")
                        and reuse_metadata.get("prefix_token_count")
                        == prefix_seed.get("prefix_token_count")
                        else "pending-request-resume"
                        if prefix_hit
                        else prefix_reason
                        if prefix_reason != "eligible-prefix"
                        else "seed-not-applied"
                    ),
                    "conversation_id": conversation_id,
                    "prefix_tokens": reused_prefix_tokens,
                    "reused_stages": reused_stage_count,
                    "completion_field_epoch_sha256": field_epoch_after,
                },
            },
        }

    def close(self) -> None:
        self._resident_prefix_cache.clear()
        self._latest_resident_prefix.clear()
        self._closed = True
        if self._executor is not None:
            close = getattr(self._executor, "close", None)
            if callable(close):
                close()
            self._executor = None


__all__ = ["DEFAULT_MODEL_NAME", "CLIENT_SCHEMA", "ResidentQwenClient", "ResidentQwenUnavailable"]
