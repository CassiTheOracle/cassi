"""Field-scheduled, single-stage Qwen3.5 resident executor.

This module deliberately does not depend on the llama inference API.  It owns
one numerical stage per call; token progression and stage ordering remain in
the field program.  Quantized model weights are supplied by ``WeightBank`` and
all mutable activations are committed as immutable snapshots.
"""
from __future__ import annotations

import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, Mapping, MutableMapping, Sequence

import numpy as np

from programs.python.records import canonical_json_bytes, digest_value

try:  # imported lazily as well, so metadata-only fixtures remain usable
    from .weight_bank import WeightBank
except ImportError:  # pragma: no cover - sibling may be added after this module
    WeightBank = None  # type: ignore[assignment,misc]
_STAGES = {
    "qwen-embedding",
    "qwen-attention",
    "qwen-ffn",
    "qwen-head",
    "qwen-route",
    "qwen-experts",
    "qwen-layer",
    "qwen-attention-route",
}
_MAX_STAGE_COHORT_WIDTH = 8

REQUEST_SCHEMA = "cassifi.resident-model-stage-request.v1"
RESULT_SCHEMA = "cassifi.resident-model-stage-result.v1"
EXECUTOR_ID = "cassi-resident-qwen"
VISUAL_STAGE_REQUEST_SCHEMA = "cassifi.resident-qwen-visual-stage-request.v1"
VISUAL_STAGE_RESULT_SCHEMA = "cassifi.resident-qwen-visual-stage-result.v1"
_ARCHITECTURES = {"qwen35", "qwen35moe"}
NEURAL_MEMBRANE_SITE_KINDS = frozenset(
    {
        "embedding",
        "vision.patch",
        "vision.merge",
        "attention.input",
        "attention.normalized",
        "attention.q",
        "attention.k",
        "attention.v",
        "attention.rope-q",
        "attention.rope-k",
        "attention.scores",
        "attention.key-cache",
        "attention.value-cache",
        "attention.probabilities",
        "attention.context",
        "attention.gate",
        "attention.gate-activation",
        "attention.gated-context",
        "attention.projected",
        "recurrent.raw-qkv",
        "recurrent.conv-history",
        "recurrent.convolved-qkv",
        "recurrent.q",
        "recurrent.k",
        "recurrent.v",
        "recurrent.beta",
        "recurrent.alpha",
        "recurrent.decay",
        "recurrent.decayed-state",
        "recurrent.prediction",
        "recurrent.z-gate",
        "recurrent.readout",
        "recurrent.normalized",
        "recurrent.state",
        "recurrent.z-activation",
        "recurrent.gated-output",
        "recurrent.delta",
        "recurrent.projected",
        "ffn.residual",
        "ffn.normalized",
        "ffn.router-logits",
        "ffn.router-probabilities",
        "ffn.expert-weights",
        "ffn.expert-gate",
        "ffn.expert-up",
        "ffn.expert-silu",
        "ffn.expert-down",
        "ffn.expert-weighted",
        "ffn.shared-gate",
        "ffn.shared-selector",
        "ffn.shared-selector-activation",
        "ffn.shared-up",
        "ffn.shared-silu",
        "ffn.shared-down",
        "ffn.shared-weighted",
        "ffn.dense-gate",
        "ffn.dense-up",
        "ffn.dense-silu",
        "ffn.dense-down",
        "ffn.output",
        "layer.output",
        "head.input",
        "head.normalized",
        "head.logits",
        "head.probabilities",
    }
)


class ResidentQwenError(ValueError):
    """Invalid request, model identity, shape, or unsupported architecture."""

class _RecurrentReadoutRefusal(ResidentQwenError):
    """Candidate support or preview failed; execute the native recurrent step."""


_StageCohortObserver = Callable[[int, str, Any, str], None]
_STAGE_DISPATCH_CONTEXT: ContextVar[tuple[str, _StageCohortObserver | None]] = (
    ContextVar("resident_qwen_stage_dispatch", default=("background", None))
)


@contextmanager
def stage_dispatch_priority(
    priority: str = "background",
    *,
    cohort_observer: _StageCohortObserver | None = None,
) -> Iterator[None]:
    """Set dispatch priority and optionally observe actual compatible cohorts.

    `cohort_observer` is called once per successfully executed row with
    `(width, stage, layer, source_sha256)`. Observer failures do not change the
    stage's execution or transaction outcome.
    """
    if not isinstance(priority, str) or priority not in {"foreground", "background"}:
        raise ResidentQwenError("stage dispatch priority must be foreground or background")
    if cohort_observer is not None and not callable(cohort_observer):
        raise ResidentQwenError("cohort_observer must be callable or null")
    token = _STAGE_DISPATCH_CONTEXT.set((priority, cohort_observer))
    try:
        yield
    finally:
        _STAGE_DISPATCH_CONTEXT.reset(token)


def _observe_stage_cohort(
    observer: _StageCohortObserver | None,
    width: int,
    request: Mapping[str, Any],
) -> None:
    if observer is None:
        return
    try:
        observer(
            width,
            str(request.get("stage", "")),
            request.get("layer"),
            str(request.get("source_sha256", "")),
        )
    except Exception:
        pass


def _cancel_requested(cancel_event: Any) -> bool:
    """True when a caller-supplied cancellation event has been raised."""
    is_set = getattr(cancel_event, "is_set", None)
    if not callable(is_set):
        return False
    try:
        return bool(is_set())
    except Exception:
        return False


def _active_work_trace() -> Any | None:
    """The active CassiFI work trace, or None when ordinary work is untraced.

    The trace module lives at the CassiFI root, so a metadata-only fixture that
    imports this module without that root stays usable; recording is optional
    and never changes a stage's execution or transaction outcome.
    """
    try:
        from cassi_work_trace import active_trace
    except ImportError:  # pragma: no cover - trace is optional for fixtures
        return None
    try:
        return active_trace()
    except Exception:  # pragma: no cover - a broken trace must not fail work
        return None


def _trace_record(
    trace: Any | None,
    kind: str,
    name: str,
    duration_ns: int = 0,
    **fields: Any,
) -> None:
    if trace is None:
        return
    try:
        trace.record(kind, name, duration_ns, **fields)
    except Exception:
        pass


def _finite_array(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 0 or not np.all(np.isfinite(arr)):
        raise ResidentQwenError(f"{name} must be a finite non-scalar array")
    return np.ascontiguousarray(arr, dtype=np.float32)


def _graph_f32_payload(value: np.ndarray) -> dict[str, Any]:
    array = np.asarray(value, dtype="<f4", order="C")
    raw = array.tobytes(order="C")
    return {
        "data_b64": base64.b64encode(raw).decode("ascii"),
        "shape": list(array.shape),
        "dtype": "<f4",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _graph_state_descriptor(value: np.ndarray) -> dict[str, Any]:
    array = np.asarray(value, dtype="<f4", order="C")
    raw = array.tobytes(order="C")
    return {
        "shape": list(array.shape), "dtype": "<f4", "order": "C",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

def _plain(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -80.0, 80.0)))

def _sample_logits(logits: np.ndarray, sampler: Mapping[str, Any]) -> int:
    mode = str(sampler.get("mode", "greedy"))
    values = np.asarray(logits, dtype=np.float32).reshape(-1)
    if mode == "greedy":
        return int(np.argmax(values))
    if mode not in {"categorical", "temperature"}:
        raise ResidentQwenError(f"unsupported sampler mode {mode!r}")
    temperature = float(sampler.get("temperature", 1.0))
    if not math.isfinite(temperature) or temperature <= 0:
        raise ResidentQwenError("sampler temperature must be positive")
    probabilities = _softmax(values / np.float32(temperature))
    top_k = int(sampler.get("top_k", 0))
    if top_k > 0 and top_k < probabilities.size:
        ids = np.argsort(probabilities)[-top_k:]
        probabilities = probabilities[ids]
        probabilities /= np.sum(probabilities, dtype=np.float32)
    else:
        ids = np.arange(probabilities.size)
    draw = float(sampler.get("draw", 0.0))
    if not math.isfinite(draw) or draw < 0 or draw >= 1:
        raise ResidentQwenError("categorical sampler requires draw in [0,1)")
    return int(ids[min(len(ids) - 1, int(np.searchsorted(np.cumsum(probabilities), draw, side="right")))])


def _silu(x: np.ndarray) -> np.ndarray:
    return x * np.asarray(_sigmoid(x), dtype=np.float32)


def _conv_window(history: np.ndarray | None, rows: int, channels: int) -> np.ndarray:
    """Return GGML's causal-convolution state: the latest rows, zero before the first token."""
    window = np.zeros((rows, channels), dtype=np.float32)
    if history is not None and rows:
        recent = np.asarray(history, dtype=np.float32).reshape(-1, channels)[-rows:]
        window[rows - recent.shape[0]:] = recent
    return window


def _softmax(x: np.ndarray) -> np.ndarray:
    z = x.astype(np.float32, copy=False)
    z = z - np.max(z)
    e = np.exp(z, dtype=np.float32)
    return e / np.sum(e, dtype=np.float32)


class _InlineSnapshotStore:
    """Small-fixture fallback; production imports ``SnapshotStore``."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        arrays: Mapping[str, np.ndarray],
        metadata: Mapping[str, Any],
        *,
        reuse_immutable_arrays: bool = False,
        durable: bool = True,
    ) -> Mapping[str, Any]:
        del reuse_immutable_arrays, durable
        clean = {str(k): _finite_array(v, name=str(k)) for k, v in arrays.items()}
        body = {
            "schema": "cassifi.resident-snapshot.inline.v1",
            "metadata": _plain(metadata),
            "arrays": {k: {"shape": list(v.shape), "dtype": "float32", "values": v.tolist()} for k, v in sorted(clean.items())},
        }
        digest = digest_value(body)
        return {"schema": body["schema"], "snapshot_sha256": digest, "metadata": body["metadata"], "arrays": body["arrays"]}

    def make_durable(self, descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
        """Inline descriptors carry their values, so nothing needs flushing."""
        return descriptor

    def load(self, descriptor: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        if not isinstance(descriptor, Mapping) or "arrays" not in descriptor:
            raise ResidentQwenError("snapshot descriptor is invalid")
        arrays = {}
        for name, spec in descriptor["arrays"].items():
            arr = _finite_array(spec.get("values"), name=str(name))
            if tuple(arr.shape) != tuple(int(i) for i in spec.get("shape", arr.shape)):
                raise ResidentQwenError("snapshot array shape is invalid")
            arrays[str(name)] = arr
        return arrays, dict(descriptor.get("metadata", {}))




@dataclass(frozen=True)
class _ModelInfo:
    architecture: str
    source_id: str
    source_sha256: str
    metadata: Mapping[str, Any]
    tensors: Mapping[str, Mapping[str, Any]]


class _ArrayBank:
    """WeightBank-compatible numerical bank for injected fixtures."""

    backend = "cpu"

    def __init__(self, tensors: Mapping[str, Any]):
        self.tensors = {str(k): np.asarray(v, dtype=np.float32) for k, v in tensors.items()}

    def _get(self, name: str) -> np.ndarray:
        if name not in self.tensors:
            raise ResidentQwenError(f"required tensor {name!r} is absent")
        arr = self.tensors[name]
        if not np.all(np.isfinite(arr)):
            raise ResidentQwenError(f"tensor {name!r} is non-finite")
        return arr

    def vector(self, name: str) -> np.ndarray:
        return np.ascontiguousarray(self._get(name).reshape(-1), dtype=np.float32)

    def embedding(self, name: str, token: int) -> np.ndarray:
        table = self._get(name)
        if table.ndim != 2:
            raise ResidentQwenError(f"embedding {name!r} must be rank two")
        if not 0 <= token < table.shape[0]:
            raise ResidentQwenError("token is outside embedding vocabulary")
        return np.ascontiguousarray(table[token], dtype=np.float32)

    def matvec(self, name: str, x: np.ndarray, expert: int | None = None) -> np.ndarray:
        w = self._get(name)
        if expert is not None and w.ndim == 3:
            if not 0 <= expert < w.shape[0]:
                raise ResidentQwenError("expert index is outside tensor")
            w = w[expert]
        if w.ndim != 2:
            raise ResidentQwenError(f"matvec tensor {name!r} must be rank two or expert rank three")
        x = np.asarray(x, dtype=np.float32).reshape(-1)
        if w.shape[1] == x.size:
            return np.asarray(w @ x, dtype=np.float32)
        if w.shape[0] == x.size:  # tolerate fixture matrices in [input, output] form
            return np.asarray(x @ w, dtype=np.float32)
        raise ResidentQwenError(f"matvec input width does not match {name!r}")
    def matvec_batch(
        self, name: str, inputs: np.ndarray, expert: int | None = None
    ) -> np.ndarray:
        matrix = np.asarray(inputs, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] < 1:
            raise ResidentQwenError("matvec_batch input must be a non-empty matrix")
        return np.stack(
            [self.matvec(name, row, expert=expert) for row in matrix],
            axis=0,
        )

    def close(self) -> None:
        return None


class _ProjectionBatcher:
    """Coalesce concurrent same-weight stage projections across independent rows."""

    def __init__(
        self,
        bank: Any,
        participant_count: int,
        *,
        wait_seconds: float = 0.002,
        work_trace: Any | None = None,
    ):
        self.bank = bank
        self.participant_count = participant_count
        self.wait_seconds = wait_seconds
        self.work_trace = work_trace
        self._lock = threading.Lock()
        self._pending: dict[tuple[str, int], dict[str, Any]] = {}

    def _run_single_expert(
        self, name: str, entries: list[dict[str, Any]], expert: int | None
    ) -> list[np.ndarray]:
        """Existing same-expert path: one native matvec/matvec_batch call."""
        if len(entries) == 1:
            return [
                self.bank.matvec(name, entries[0]["input"], expert=expert)
            ]
        inputs = np.stack([entry["input"] for entry in entries], axis=0)
        batch_matvec = getattr(self.bank, "matvec_batch", None)
        if callable(batch_matvec):
            outputs = list(batch_matvec(name, inputs, expert=expert))
        else:
            outputs = [
                self.bank.matvec(name, row, expert=expert)
                for row in inputs
            ]
        if len(outputs) != len(entries):
            raise ResidentQwenError(
                "WeightBank.matvec_batch returned the wrong row count"
            )
        return outputs

    def _flush(self, group: dict[str, Any]) -> None:
        entries = group["entries"]
        trace = self.work_trace
        started_ns = trace.now() if trace is not None else 0
        distinct_experts: list[Any] = []
        try:
            experts = [entry["expert"] for entry in entries]
            for expert in experts:
                if expert not in distinct_experts:
                    distinct_experts.append(expert)
            if len(distinct_experts) == 1:
                outputs = self._run_single_expert(
                    group["name"], entries, distinct_experts[0]
                )
            else:
                # Cross-expert group: every routed row of this stage batch is
                # one grouped native call, preserving per-row results.
                inputs = np.stack([entry["input"] for entry in entries], axis=0)
                batch_experts = getattr(self.bank, "matvec_batch_experts", None)
                if callable(batch_experts):
                    outputs = list(batch_experts(group["name"], inputs, experts))
                    if len(outputs) != len(entries):
                        raise ResidentQwenError(
                            "WeightBank.matvec_batch_experts returned the wrong row count"
                        )
                else:
                    outputs = [None] * len(entries)
                    for expert in distinct_experts:
                        indices = [
                            index
                            for index, value in enumerate(experts)
                            if value == expert
                        ]
                        sub_outputs = self._run_single_expert(
                            group["name"],
                            [entries[index] for index in indices],
                            expert,
                        )
                        for index, output in zip(indices, sub_outputs):
                            outputs[index] = output
            for entry, output in zip(entries, outputs):
                entry["output"] = np.asarray(output, dtype=np.float32).reshape(-1)
        except BaseException as exc:
            for entry in entries:
                entry["error"] = exc
        finally:
            if trace is not None:
                meta: dict[str, Any] = {
                    "expert": (
                        distinct_experts[0] if len(distinct_experts) == 1 else None
                    ),
                    "grouped": len(entries) > 1,
                    "failed": any(entry.get("error") is not None for entry in entries),
                }
                if len(distinct_experts) > 1:
                    meta["experts"] = list(distinct_experts)
                _trace_record(
                    trace,
                    "projection",
                    str(group["name"]),
                    max(0, trace.now() - started_ns),
                    rows=len(entries),
                    items=1,
                    meta=meta,
                )
            for entry in entries:
                entry["done"].set()

    def matvec(self, name: str, x: np.ndarray, expert: int | None = None) -> np.ndarray:
        vector = np.asarray(x, dtype=np.float32)
        trace = self.work_trace
        if vector.ndim != 1:
            return self.bank.matvec(name, vector, expert=expert)
        try:
            key = (str(name), int(vector.size))
            hash(key)
        except (TypeError, ValueError):
            return self.bank.matvec(name, vector, expert=expert)
        submitted_ns = trace.now() if trace is not None else 0
        entry: dict[str, Any] = {
            "input": vector,
            "expert": expert,
            "done": threading.Event(),
            "output": None,
            "error": None,
        }
        flush_group = None
        with self._lock:
            group = self._pending.get(key)
            if group is None:
                group = {
                    "name": name,
                    "entries": [],
                    "flushing": False,
                }
                self._pending[key] = group
            group["entries"].append(entry)
            if (
                len(group["entries"]) >= self.participant_count
                and not group["flushing"]
            ):
                group["flushing"] = True
                self._pending.pop(key, None)
                flush_group = group
        if flush_group is None and not entry["done"].wait(self.wait_seconds):
            with self._lock:
                if not entry["done"].is_set() and not group["flushing"]:
                    group["flushing"] = True
                    if self._pending.get(key) is group:
                        self._pending.pop(key, None)
                    flush_group = group
        # The flushing row's own execution is recorded as projection work.
        waited_ns = trace.now() if trace is not None else 0
        if flush_group is not None:
            self._flush(flush_group)
        else:
            entry["done"].wait()
            waited_ns = trace.now() if trace is not None else 0
        if trace is not None:
            _trace_record(
                trace,
                "wait",
                "projection-group",
                wait_ns=max(0, waited_ns - submitted_ns),
                rows=1,
                meta={"expert": expert, "tensor": str(name)},
            )
        if entry["error"] is not None:
            raise entry["error"]
        output = entry["output"]
        if not isinstance(output, np.ndarray):
            raise ResidentQwenError("batched WeightBank projection produced no output")
        return output


class _BatchedWeightBank:
    def __init__(self, bank: Any, batcher: _ProjectionBatcher):
        self._base_bank = bank
        self._batcher = batcher

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_bank, name)

    def matvec(self, name: str, x: np.ndarray, expert: int | None = None) -> np.ndarray:
        return self._batcher.matvec(name, x, expert=expert)

    def matvec_many(self, requests: Sequence[tuple[str, int | None]], x: np.ndarray) -> list[np.ndarray]:
        return [
            self.matvec(name, x, expert=expert)
            for name, expert in requests
        ]
class ResidentQwenExecutor:
    """Execute field-selected Qwen stages and isolated multi-row stage batches."""

    # Transaction contexts defer flushing; the owner seals the snapshot its
    # durable record references through ``seal_stage_transaction``.
    _defer_snapshot_durability = False

    def __init__(self, model_path: str | Path | Mapping[str, Any], state_directory: str | Path, *, backend: str = "cpu", library_path: str | Path | None = None, threads: int = 8, manifest: Mapping[str, Any] | None = None, projector_path: str | Path | None = None, physical_admission: Any | None = None):
        self.backend = str(backend)
        self._physical_admission = physical_admission
        self._library_path = (
            None if library_path is None else Path(library_path).expanduser().resolve()
        )
        self._projector_path = (
            None
            if projector_path is None
            else Path(projector_path).expanduser().resolve()
        )
        self._threads = threads
        if isinstance(model_path, Mapping):
            injected = dict(model_path)
            metadata = dict(injected.get("metadata", {}))
            tensors = injected.get("tensors", {})
            architecture = str(metadata.get("general.architecture", injected.get("architecture", "")))
            source_sha256 = str(injected.get("source_sha256", digest_value({"metadata": metadata, "tensors": _plain(tensors)})))
            self._model_path = None
            self._manifest = None
            self._model = _ModelInfo(architecture, str(injected.get("source_id", "fixture")), source_sha256, metadata, {})
            self._bank = _ArrayBank(tensors)
            self._tensor_shapes = {str(k): {"shape": list(np.asarray(v).shape), "byte_length": int(np.asarray(v).nbytes)} for k, v in tensors.items()}
        else:
            path = Path(model_path).resolve(strict=True)
            if not path.is_file():
                raise ResidentQwenError("model_path is not a regular file")
            from .gguf import inspect_gguf, reuse_verified_manifest
            manifest = (
                dict(reuse_verified_manifest(path, manifest))
                if manifest is not None
                else inspect_gguf(path)
            )
            metadata_value = manifest.get("model_metadata")
            if not isinstance(metadata_value, Mapping):
                raise ResidentQwenError("GGUF manifest has no model metadata")
            metadata = dict(metadata_value)
            architecture = str(metadata.get("general.architecture", ""))
            source_sha256 = str(manifest["source_sha256"])
            self._model_path = path
            self._manifest = manifest
            self._model = _ModelInfo(architecture, str(manifest["source_id"]), source_sha256, metadata, {str(t["name"]): t for t in manifest["tensors"]})
            self._tensor_shapes = self._model.tensors
            if WeightBank is None:
                raise ResidentQwenError("WeightBank is unavailable for GGUF execution")
            self._bank = WeightBank(
                path,
                backend=backend,
                library_path=library_path,
                threads=threads,
                manifest=manifest,
            )
        self._logical_weight_bytes = int(
            sum(
                int(tensor.get("byte_length", 0))
                for tensor in self._tensor_shapes.values()
            )
        )
        bank_source = getattr(self._bank, "source_sha256", None)
        if bank_source is not None and str(bank_source) != self._model.source_sha256:
            raise ResidentQwenError("WeightBank source identity does not match GGUF manifest")
        self._tokenizer = None
        if self._model_path is not None:
            try:
                from .tokenizer import GGUFTokenizer
                self._tokenizer = GGUFTokenizer(self._model_path)
            except (ImportError, OSError, ValueError):
                self._tokenizer = None
        self._state_directory = Path(state_directory)
        try:
            from .state_backing import SnapshotStore
            self._snapshots = SnapshotStore(self._state_directory)
        except (ImportError, TypeError):
            self._snapshots = _InlineSnapshotStore(self._state_directory)
        self._request_tensor_names: Mapping[str, Any] = {}
        self._resident_experts: dict[int, set[int]] = {}
        self._working_snapshot: Mapping[str, Any] | None = None
        self._working_arrays: dict[str, np.ndarray] | None = None
        self._working_metadata: dict[str, Any] | None = None
        self.working_snapshot_hits = 0
        self._closed = False
        self._vision_encoder: Any | None = None
        self._visual_embedding_sets: dict[str, np.ndarray] = {}
        self._volatile_visual_snapshots: dict[
            str, tuple[dict[str, Any], dict[str, np.ndarray], dict[str, Any]]
        ] = {}
        self._volatile_visual_checkpoints: dict[
            str, tuple[dict[str, Any], dict[str, np.ndarray], dict[str, Any]]
        ] = {}
        self._volatile_visual_previous: dict[
            str, tuple[dict[str, Any], dict[str, np.ndarray], dict[str, Any]]
        ] = {}
        self._volatile_snapshot_sequence = 0
        self._activation_exchange: Callable[[str, np.ndarray], np.ndarray] | None = None
        self._device_epoch: Any | None = None
        self._device_membrane: Any | None = None
        self._stage_transaction_guard = threading.RLock()
        self._stage_transactions: dict[str, dict[str, Any]] = {}
        self._graph_site_candidate_provider: Callable[
            [Mapping[str, Any], Mapping[str, np.ndarray], Mapping[str, Any]],
            Mapping[str, Any] | list[Mapping[str, Any]] | None,
        ] | None = None
        self._batch_join_condition = threading.Condition()
        self._batch_join_groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._batch_join_ticket_counts: dict[str, int] = {}
        self._batch_join_window_seconds = 0.003

    @property
    def source_sha256(self) -> str:
        return self._model.source_sha256

    @property
    def architecture(self) -> str:
        return self._model.architecture

    @property
    def neural_membrane_mode_count(self) -> int:
        """Physical modes in one membrane bank; wider vectors are chunked."""

        return 65_536

    def ensure_visual_encoder(self) -> Any:
        """Lazily load and verify the selected native visual projector."""

        if self._closed:
            raise ResidentQwenError("executor is closed")
        if self._vision_encoder is None:
            if self._projector_path is None:
                raise ResidentQwenError("no Qwen vision projector was configured")
            try:
                from .qwen_vision import QwenVisionEncoder
                self._vision_encoder = QwenVisionEncoder(
                    self._projector_path,
                    backend="auto",
                    threads=self._threads,
                    library_path=self._library_path,
                )
            except Exception as exc:
                raise ResidentQwenError(
                    f"Qwen vision projector could not be opened: {exc}"
                ) from exc
        return self._vision_encoder
    def bind_visual_encoder(self, encoder: Any) -> None:
        """Bind the resident client's single verified encoder instance."""

        if self._closed:
            raise ResidentQwenError("executor is closed")
        projector_sha256 = getattr(encoder, "projector_sha256", None)
        if (
            not isinstance(projector_sha256, str)
            or len(projector_sha256) != 64
            or any(character not in "0123456789abcdef" for character in projector_sha256)
        ):
            raise ResidentQwenError("bound Qwen vision encoder is not verified")
        if self._vision_encoder is not None and self._vision_encoder is not encoder:
            raise ResidentQwenError("executor already owns a different vision encoder")
        self._vision_encoder = encoder
    def register_visual_embeddings(
        self, reference_id: str, embeddings: np.ndarray
    ) -> None:
        """Install one request-scoped matrix without serializing it into field state."""

        if self._closed:
            raise ResidentQwenError("executor is closed")
        if not isinstance(reference_id, str) or not reference_id or len(reference_id) > 128:
            raise ResidentQwenError("visual embedding reference is invalid")
        matrix = np.asarray(embeddings, dtype=np.float32)
        expected = int(
            self._meta(
                f"{self.architecture}.embedding_length",
                self._meta("embedding_length", 0),
            )
        )
        if (
            matrix.ndim != 2
            or matrix.shape[0] < 1
            or matrix.shape[1] != expected
            or matrix.size > 1_048_576
            or not np.isfinite(matrix).all()
        ):
            raise ResidentQwenError("visual embedding matrix is invalid")
        matrix = np.ascontiguousarray(matrix)
        previous = self._visual_embedding_sets.get(reference_id)
        if previous is not None and not np.array_equal(previous, matrix):
            raise ResidentQwenError(
                "visual embedding reference is already bound to different content"
            )
        if reference_id not in self._visual_embedding_sets:
            if len(self._visual_embedding_sets) >= 8:
                raise ResidentQwenError(
                    "resident executor already has eight transient visual requests"
                )
            self._visual_embedding_sets[reference_id] = matrix
    def retain_visual_snapshot(self, reference_id: str, descriptor: Any) -> None:
        """Keep the field's input snapshot through its next published continuation."""

        if reference_id not in self._visual_embedding_sets:
            raise ResidentQwenError("visual token batch has no live embedding matrix")
        if descriptor is None or descriptor == {}:
            self._volatile_visual_checkpoints.pop(reference_id, None)
            return
        if not isinstance(descriptor, Mapping):
            raise ResidentQwenError("visual token batch snapshot is invalid")
        requested = _plain(dict(descriptor))
        current = self._volatile_visual_snapshots.get(reference_id)
        retained = self._volatile_visual_checkpoints.get(reference_id)
        if current is not None and current[0] == requested:
            self._volatile_visual_checkpoints[reference_id] = current
        elif retained is None or retained[0] != requested:
            raise ResidentQwenError("visual token batch input snapshot is unavailable")

    def commit_visual_snapshot(self, reference_id: str) -> None:
        """End the owner transaction without dropping its replayable input."""

        latest = self._volatile_visual_snapshots.get(reference_id)
        if (
            latest is not None
            and self._working_snapshot is not None
            and self._working_snapshot.get("visual_embedding_id") == reference_id
            and self._working_snapshot != latest[0]
        ):
            self._working_snapshot = None
            self._working_arrays = None
            self._working_metadata = None

    def clear_visual_embeddings(self, reference_id: str) -> None:
        self._visual_embedding_sets.pop(reference_id, None)
        self._volatile_visual_snapshots.pop(reference_id, None)
        self._volatile_visual_previous.pop(reference_id, None)
        self._volatile_visual_checkpoints.pop(reference_id, None)
        descriptor = self._working_snapshot
        if (
            isinstance(descriptor, Mapping)
            and descriptor.get("visual_embedding_id") == reference_id
        ):
            self._working_snapshot = None
            self._working_arrays = None
            self._working_metadata = None

    def _visual_embedding(self, reference_id: Any, index: Any) -> np.ndarray:
        if (
            not isinstance(reference_id, str)
            or not reference_id
            or isinstance(index, bool)
            or not isinstance(index, int)
        ):
            raise ResidentQwenError("visual embedding reference is malformed")
        matrix = self._visual_embedding_sets.get(reference_id)
        if matrix is None:
            raise ResidentQwenError(
                "visual placeholder has no live authorized embedding matrix"
            )
        if not 0 <= index < matrix.shape[0]:
            raise ResidentQwenError("visual embedding position is outside the live matrix")
        return matrix[index]

    @staticmethod
    def _is_neural_site_kind(kind: str) -> bool:
        if kind in NEURAL_MEMBRANE_SITE_KINDS:
            return True
        if not kind.startswith("vision.block."):
            return False
        index = kind.removeprefix("vision.block.")
        return index.isdecimal() and str(int(index)) == index and int(index) < 256
    @staticmethod
    def _neural_site(
        kind: str,
        *,
        head: int | None = None,
        layer: int | None = None,
        expert: int | None = None,
    ) -> str:
        if not ResidentQwenExecutor._is_neural_site_kind(kind):
            raise ResidentQwenError(f"undeclared neural membrane site {kind!r}")
        qualifiers = []
        if layer is not None:
            qualifiers.append(f"layer={int(layer)}")
        if head is not None:
            qualifiers.append(f"head={int(head)}")
        if expert is not None:
            qualifiers.append(f"expert={int(expert)}")
        return kind + (":" + ":".join(qualifiers) if qualifiers else "")

    def _exchange(
        self,
        kind: str,
        activation: np.ndarray,
        *,
        head: int | None = None,
        layer: int | None = None,
        expert: int | None = None,
    ) -> np.ndarray:
        """Exchange one complete vector with the active owner-field epoch."""

        if not self._is_neural_site_kind(kind):
            raise ResidentQwenError(f"undeclared neural membrane site {kind!r}")
        value = _finite_array(activation, name=f"activation {kind}")
        callback = self._activation_exchange
        if callback is None:
            return value
        site = self._neural_site(kind, head=head, layer=layer, expert=expert)
        exchanged = _finite_array(callback(site, value), name=f"field response {site}")
        if exchanged.shape != value.shape:
            raise ResidentQwenError(
                f"field response shape disagrees at neural site {site!r}"
            )
        return exchanged

    def _exchange_device(
        self,
        kind: str,
        activation: Any,
        *,
        layer: int | None = None,
        expert: int | None = None,
    ) -> Any:
        return self._device_membrane.device_exchange(
            self._neural_site(kind, layer=layer, expert=expert), activation
        )

    def _meta(self, name: str, default: Any = None) -> Any:
        return self._model.metadata.get(name, default)

    def _validate_metadata(self) -> None:
        required = ["embedding_length", "block_count", "context_length"]
        prefix = self._model.architecture
        missing = [f"{prefix}.{name}" for name in required if self._meta(f"{prefix}.{name}") is None]
        # Fixtures may provide the same dimensions without the architecture prefix.
        if missing and not all(self._meta(name) is not None for name in required):
            raise ResidentQwenError("GGUF is missing required Qwen metadata: " + ", ".join(missing))
        dim = int(self._meta(f"{prefix}.embedding_length", self._meta("embedding_length", 0)))
        blocks = int(self._meta(f"{prefix}.block_count", self._meta("block_count", 0)))
        context = int(self._meta(f"{prefix}.context_length", self._meta("context_length", 0)))
        if dim <= 0 or blocks <= 0 or context <= 0:
            raise ResidentQwenError("Qwen metadata dimensions must be positive")
        if self._meta(f"{prefix}.attention.head_count", self._meta("attention.head_count")) is not None:
            nh = int(self._meta(f"{prefix}.attention.head_count", self._meta("attention.head_count")))
            nk = int(self._meta(f"{prefix}.attention.head_count_kv", self._meta("attention.head_count_kv", nh)))
            if nh <= 0 or nk <= 0 or nh % nk:
                raise ResidentQwenError("Qwen attention head counts are not valid GQA")

    def _weight(self, stem: str, layer: int | None = None, *, required: bool = True) -> str | None:
        aliases = {
            "attn_out": ("attn_out", "attn_output"),
            "output": ("output", "output_head", "token_embd"),
            "ffn_norm": ("ffn_norm", "attn_post_norm", "post_attention_norm"),
            "ssm_dt": ("ssm_dt.bias", "ssm_dt"),
        }.get(stem, (stem,))
        requested = getattr(self, "_request_tensor_names", {})
        requested_names = requested.get(stem, ()) if isinstance(requested, Mapping) else ()
        if isinstance(requested_names, str):
            requested_names = (requested_names,)
        candidates: list[str] = [str(n) for n in requested_names]
        for alias in aliases:
            if layer is not None:
                candidates.extend([f"blk.{layer}.{alias}.weight", f"blk.{layer}.{alias}", f"layers.{layer}.{alias}.weight"])
            candidates.extend([f"{alias}.weight", alias])
        seen: set[str] = set()
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            if c in self._tensor_shapes or (isinstance(self._bank, _ArrayBank) and c in self._bank.tensors):
                return c
        if required:
            raise ResidentQwenError(f"required Qwen tensor is absent: {candidates[0] if candidates else stem!r}")
        return None

    def _vec(self, stem: str, layer: int | None = None, *, required: bool = True) -> np.ndarray | None:
        name = self._weight(stem, layer, required=required)
        if name is None:
            return None
        return np.asarray(self._bank.vector(name), dtype=np.float32)
    def _tensor(self, name: str) -> np.ndarray:
        bank = getattr(self._bank, "_base_bank", self._bank)
        if isinstance(bank, _ArrayBank):
            return np.asarray(bank.tensors[name], dtype=np.float32)
        method = getattr(bank, "tensor", None)
        if method is None:
            raise ResidentQwenError("WeightBank.tensor is required for recurrent convolution tensors")
        return np.asarray(method(name), dtype=np.float32)

    def _conv_history_rows(self, layer: int, channels: int) -> int:
        """Rows of recurrent convolution state: kernel taps minus the current sample."""
        name = self._weight("ssm_conv1d", layer, required=False)
        if name is None:
            return 0
        taps, remainder = divmod(
            int(np.prod(self._tensor_shapes[name]["shape"], dtype=np.int64)), channels,
        )
        if remainder or taps < 1:
            raise ResidentQwenError("recurrent convolution kernel does not match the QKV width")
        return taps - 1

    def _mat(self, stem: str, x: np.ndarray, layer: int | None = None, *, expert: int | None = None, required: bool = True) -> np.ndarray | None:
        name = self._weight(stem, layer, required=required)
        if name is None:
            return None
        return np.asarray(self._bank.matvec(name, np.asarray(x, dtype=np.float32), expert=expert), dtype=np.float32).reshape(-1)

    def _mat_many(
        self,
        requests: Sequence[tuple[str, int | None]],
        x: np.ndarray,
        layer: int | None = None,
        *,
        required: bool | Sequence[bool] = True,
    ) -> list[np.ndarray | None]:
        """Evaluate independent projections sharing one input in request order."""
        if isinstance(required, bool):
            required_flags = [required] * len(requests)
        else:
            required_flags = [bool(value) for value in required]
            if len(required_flags) != len(requests):
                raise ResidentQwenError("matvec_many required flags do not match requests")
        results: list[np.ndarray | None] = [None] * len(requests)
        resolved: list[tuple[int, str, int | None, str]] = []
        for index, ((stem, expert), is_required) in enumerate(zip(requests, required_flags)):
            name = self._weight(stem, layer, required=is_required)
            if name is not None:
                resolved.append((index, name, expert, stem))
        if not resolved:
            return results
        matvec_many = getattr(self._bank, "matvec_many", None)
        if not callable(matvec_many):
            for index, _name, expert, stem in resolved:
                results[index] = self._mat(
                    stem,
                    x,
                    layer,
                    expert=expert,
                    required=required_flags[index],
                )
            return results
        outputs = list(
            matvec_many(
                [(name, expert) for _index, name, expert, _stem in resolved],
                np.asarray(x, dtype=np.float32).reshape(-1),
            )
        )
        if len(outputs) != len(resolved):
            raise ResidentQwenError("WeightBank.matvec_many returned the wrong output count")
        for (index, _name, _expert, _stem), output in zip(resolved, outputs):
            results[index] = np.asarray(output, dtype=np.float32).reshape(-1)
        return results
    def _load_state(self, request: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        descriptor = request.get("snapshot")
        if descriptor is None or descriptor == {}:
            return {}, {}
        if not isinstance(descriptor, Mapping):
            raise ResidentQwenError("snapshot must be a mapping or null")
        plain_descriptor = _plain(dict(descriptor))
        is_visual = plain_descriptor.get("schema") == "cassifi.resident-qwen-volatile-snapshot.v1"
        if not is_visual and (
            self._working_snapshot is not None
            and self._working_arrays is not None
            and self._working_metadata is not None
            and plain_descriptor == self._working_snapshot
        ):
            if self._working_metadata.get("backend") not in {"cpu", "vulkan"}:
                raise ResidentQwenError("snapshot backend is invalid")
            self.working_snapshot_hits += 1
            return dict(self._working_arrays), dict(self._working_metadata)
        if is_visual:
            reference_id = plain_descriptor.get("visual_embedding_id")
            cached = (
                self._volatile_visual_snapshots.get(reference_id)
                if isinstance(reference_id, str)
                else None
            )
            if cached is None or cached[0] != plain_descriptor:
                cached = self._volatile_visual_checkpoints.get(reference_id)
            if cached is None or cached[0] != plain_descriptor:
                cached = self._volatile_visual_previous.get(reference_id)
            if cached is None or cached[0] != plain_descriptor:
                current = self._volatile_visual_snapshots.get(reference_id)
                checkpoint = self._volatile_visual_checkpoints.get(reference_id)
                previous = self._volatile_visual_previous.get(reference_id)
                raise ResidentQwenError(
                    "visual task snapshot is not live in this executor "
                    f"(stage={request.get('stage')}, position={request.get('position')}, "
                    f"requested={plain_descriptor.get('sequence')}, "
                    f"current={None if current is None else current[0].get('sequence')}, "
                    f"checkpoint={None if checkpoint is None else checkpoint[0].get('sequence')}, "
                    f"previous={None if previous is None else previous[0].get('sequence')})"
                )
            if (
                self._working_snapshot == plain_descriptor
                and self._working_arrays is not None
                and self._working_metadata is not None
            ):
                if self._working_metadata.get("backend") != self.backend:
                    raise ResidentQwenError("transient visual snapshot cannot change backend")
                self.working_snapshot_hits += 1
                return dict(self._working_arrays), dict(self._working_metadata)
            arrays, metadata = dict(cached[1]), dict(cached[2])
        else:
            arrays, metadata = self._snapshots.load(descriptor)
        if metadata.get("source_sha256", self.source_sha256) != self.source_sha256:
            raise ResidentQwenError("snapshot source identity does not match executor model")
        if metadata.get("backend") not in {"cpu", "vulkan"}:
            raise ResidentQwenError("snapshot backend is invalid")
        if is_visual and metadata["backend"] != self.backend:
            raise ResidentQwenError("transient visual snapshot cannot change backend")
        prepared = {
            str(key): _finite_array(value, name=str(key))
            for key, value in arrays.items()
        }
        self._working_snapshot = plain_descriptor
        self._working_arrays = prepared
        self._working_metadata = dict(metadata)
        return dict(prepared), dict(metadata)

    def _save_state(self, arrays: Mapping[str, np.ndarray], request: Mapping[str, Any]) -> Mapping[str, Any]:
        metadata = {
            "source_sha256": self.source_sha256,
            "architecture": self.architecture,
            "position": int(request["position"]),
            "token": int(request["token"]),
            "stage": str(request["stage"]),
            "layer": request.get("layer"),
            "backend": self.backend,
        }
        previous_arrays = self._working_arrays
        prepared: dict[str, np.ndarray] = {}
        for key, value in arrays.items():
            name = str(key)
            # Stage kernels replace or copy state before updating it. Reuse an
            # exact read-only array from the last accepted snapshot without
            # rescanning every element; new or mutable outputs still take the
            # full finite-value validation path before publication.
            if (
                previous_arrays is not None
                and previous_arrays.get(name) is value
                and isinstance(value, np.ndarray)
                and value.dtype == np.dtype(np.float32)
                and value.ndim > 0
                and value.flags.c_contiguous
                and not value.flags.writeable
            ):
                prepared[name] = value
            else:
                checked = _finite_array(value, name=name)
                # A prepared view on a writable base can never be recognized
                # as immutable by the snapshot store, so every later save
                # rehashes it. Publish owning read-only storage instead; the
                # snapshot store then reuses the digest across saves.
                base = getattr(checked, "base", None)
                while base is not None:
                    if isinstance(base, np.ndarray) and base.flags.writeable:
                        checked = np.array(
                            checked, dtype=np.float32, copy=True, order="C"
                        )
                        break
                    base = getattr(base, "base", None)
                prepared[name] = checked
        for array in prepared.values():
            array.setflags(write=False)
        parameters = request.get("parameters")
        visual_reference = (
            parameters.get("visual_embedding_id")
            if isinstance(parameters, Mapping)
            else None
        )
        if visual_reference is not None:
            if (
                not isinstance(visual_reference, str)
                or visual_reference not in self._visual_embedding_sets
            ):
                raise ResidentQwenError(
                    "visual snapshot has no live authorized embedding matrix"
                )
            self._volatile_snapshot_sequence += 1
            descriptor = {
                "schema": "cassifi.resident-qwen-volatile-snapshot.v1",
                "visual_embedding_id": visual_reference,
                "sequence": self._volatile_snapshot_sequence,
                "source_sha256": self.source_sha256,
            }
            prior_visual = self._volatile_visual_snapshots.get(visual_reference)
            if prior_visual is not None:
                self._volatile_visual_previous[visual_reference] = prior_visual
            self._volatile_visual_snapshots[visual_reference] = (
                descriptor,
                prepared,
                dict(metadata),
            )
        else:
            descriptor = self._snapshots.save(
                prepared,
                metadata,
                reuse_immutable_arrays=True,
                durable=not self._defer_snapshot_durability,
            )
        self._working_snapshot = _plain(dict(descriptor))
        self._working_arrays = prepared
        self._working_metadata = dict(metadata)
        return descriptor

    def _norm(self, x: np.ndarray, stem: str, layer: int | None, eps: float = 1e-6) -> np.ndarray:
        w = self._vec(stem, layer)
        if w is None or w.size != x.size:
            raise ResidentQwenError(f"normalization width mismatch for {stem}")
        return x * (w / np.sqrt(np.mean(x * x, dtype=np.float32) + np.float32(eps)))

    def _is_imrope_sections(self, sections: Sequence[int], n_rot: int) -> bool:
        if len(sections) != 4 or n_rot <= 0 or n_rot % 2:
            return False
        values: list[int] = []
        for value in sections:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return False
            values.append(value)
        return sum(values) == n_rot // 2 and sum(values) > 0

    def _rope_dimension_count(self, head_width: int) -> int:
        raw = self._meta(
            f"{self.architecture}.rope.dimension_count",
            self._meta("rope.dimension_count", head_width),
        )
        if isinstance(raw, bool) or not isinstance(raw, int) or not 0 < raw <= head_width:
            raise ResidentQwenError("RoPE dimension count is outside the attention head")
        if raw % 2:
            raise ResidentQwenError("RoPE dimension count must be even")
        return raw

    def _rope(
        self,
        x: np.ndarray,
        position: int | Sequence[int],
        sections: Sequence[int] | None,
        base: float,
    ) -> np.ndarray:
        y = x.copy()
        section_values = [x.size] if sections is None else list(sections)
        pos = (
            list(position)
            if isinstance(position, Sequence) and not isinstance(position, (str, bytes))
            else [position]
        )
        if (
            not pos
            or any(isinstance(value, bool) or not isinstance(value, int) for value in pos)
        ):
            raise ResidentQwenError("RoPE position axes must be integer values")
        axes = [int(value) for value in pos]
        while len(axes) < 4:
            axes.append(axes[-1])
        n_rot = self._rope_dimension_count(x.size)
        if self._is_imrope_sections(section_values, n_rot):
            total = sum(section_values)
            sections_by_axis = section_values
            for pair in range(n_rot // 2):
                sector = pair % total
                if sector % 3 == 1 and sector < 3 * sections_by_axis[1]:
                    axis = 1
                elif sector % 3 == 2 and sector < 3 * sections_by_axis[2]:
                    axis = 2
                elif sector % 3 == 0 and sector < 3 * sections_by_axis[0]:
                    axis = 0
                else:
                    axis = 3
                theta = axes[axis] * (base ** (-2.0 * pair / n_rot))
                c, s = math.cos(theta), math.sin(theta)
                other = pair + n_rot // 2
                a, b = y[pair], y[other]
                y[pair], y[other] = np.float32(a * c - b * s), np.float32(
                    a * s + b * c
                )
            return y

        offset = 0
        for section_index, raw_width in enumerate(section_values):
            width = int(raw_width)
            if width <= 0:
                continue
            p = float(axes[min(section_index, len(axes) - 1)])
            for i in range(0, min(width, x.size - offset) - 1, 2):
                theta = p * (base ** (-2.0 * (i // 2) / max(1, width)))
                c, s = math.cos(theta), math.sin(theta)
                a, b = y[offset + i], y[offset + i + 1]
                y[offset + i], y[offset + i + 1] = np.float32(
                    a * c - b * s
                ), np.float32(a * s + b * c)
            offset += width
            if offset >= x.size:
                break
        return y

    def _embedding(self, request: Mapping[str, Any], arrays: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
        token = int(request["token"])
        parameters = request.get("parameters")
        visual_reference = (
            parameters.get("visual_embedding_id")
            if isinstance(parameters, Mapping)
            else None
        )
        has_visual_index = (
            isinstance(parameters, Mapping)
            and "visual_embedding_index" in parameters
        )
        if has_visual_index and visual_reference is None:
            raise ResidentQwenError("visual embedding index has no request reference")
        override = (
            self._visual_embedding(
                visual_reference,
                parameters.get("visual_embedding_index"),
            )
            if visual_reference is not None and has_visual_index
            else None
        )
        expected = int(self._meta(f"{self.architecture}.embedding_length", self._meta("embedding_length", 0)))
        if override is not None:
            hidden = _finite_array(override, name="visual token embedding").reshape(-1)
            if hidden.size != expected:
                raise ResidentQwenError(
                    "visual embedding width does not match model metadata"
                )
            if self._device_epoch is not None:
                device_hidden = self._device_epoch.upload(hidden)
                hidden = self._device_epoch.download(
                    self._device_membrane.device_exchange("embedding", device_hidden)
                )
            else:
                hidden = self._exchange("embedding", hidden)
        else:
            name = self._weight("token_embd", required=True)
            if self._device_epoch is not None:
                device_hidden = self._device_epoch.embedding(name, token)
                if device_hidden.count != expected:
                    raise ResidentQwenError("embedding output width does not match model metadata")
                hidden = self._device_epoch.download(
                    self._device_membrane.device_exchange("embedding", device_hidden)
                )
            else:
                hidden = np.asarray(self._bank.embedding(name, token), dtype=np.float32).reshape(-1)
                if hidden.size != expected:
                    raise ResidentQwenError("embedding output width does not match model metadata")
                hidden = self._exchange("embedding", hidden)
        arrays = dict(arrays)
        arrays.pop("logits", None)
        arrays["hidden"] = hidden
        arrays["token"] = np.asarray([token], dtype=np.float32)
        return arrays, self._save_state(arrays, request)

    def _attention_memory_site(
        self, request: Mapping[str, Any], arrays: Mapping[str, np.ndarray],
        normalized: np.ndarray, q: np.ndarray, k: np.ndarray, v: np.ndarray, layer: int,
    ) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None, Mapping[str, Any] | None]:
        site = request.get("graph_site")
        if site is None:
            return None, None, None
        from .graph_site import SITE_STAGES
        if (not isinstance(site, Mapping) or site.get("specialist") != "attention-memory"
                or request.get("stage") != SITE_STAGES.get((self.architecture, "attention-memory"))
                or request.get("layer") != layer):
            raise ResidentQwenError("attention-memory graph site is invalid")
        dependencies = site.get("dependencies")
        if not isinstance(dependencies, Mapping):
            return None, None, None
        from .graph_site import invocation
        native_state = {
            "membrane_profile": _plain(dependencies.get("membrane_profile")),
            "field_epoch_sha256": dependencies.get("field_epoch_sha256"),
        }
        binding = invocation(
            source_sha256=self.source_sha256, architecture=self.architecture,
            backend=self.backend, sequence_id=str(site.get("sequence_id", "")),
            position=int(site.get("position", -1)), stage=str(site.get("stage", "")),
            layer=layer, site=str(site.get("site", "")), specialist="attention-memory",
            predecessor_generation=int(site.get("predecessor_generation", -1)),
            predecessor_sha256=str(site.get("predecessor_snapshot_sha256", "")),
            intervention_order=int(site.get("intervention_order", -1)),
            dependencies=dependencies, request_sha256=str(request.get("request_sha256", "")),
            verb=str(site.get("verb", "observe")),
        )
        shapes = {
            "attn_q": {"shape": list(q.shape), "dtype": "<f4", "order": "C"},
            "attn_k": {"shape": list(k.shape), "dtype": "<f4", "order": "C"},
            "attn_v": {"shape": list(v.shape), "dtype": "<f4", "order": "C"},
        }
        return binding, native_state, shapes

    def _full_attention(
        self,
        x: np.ndarray,
        arrays: dict[str, np.ndarray],
        layer: int,
        position: int | Sequence[int],
        request: Mapping[str, Any] | None = None,
        graph_capture: dict[str, Any] | None = None,
    ) -> np.ndarray:
        y = self._norm(x, "attn_norm", layer, float(self._meta(f"{self.architecture}.attention.layer_norm_rms_epsilon", 1e-6)))
        y = self._exchange("attention.normalized", y, layer=layer)
        nh = int(self._meta(f"{self.architecture}.attention.head_count", self._meta("attention.head_count", 1)))
        nk = int(self._meta(f"{self.architecture}.attention.head_count_kv", self._meta("attention.head_count_kv", nh)))
        hd_meta = int(self._meta(f"{self.architecture}.attention.key_length", self._meta("attention.key_length", 0)))
        query_gate: np.ndarray | None = None
        qkv = self._mat("attn_qkv", y, layer, required=False)
        if qkv is None:
            q, k, v = self._mat_many(
                (("attn_q", None), ("attn_k", None), ("attn_v", None)),
                y,
                layer,
            )
            assert q is not None and k is not None and v is not None
            if hd_meta > 0 and q.size == 2 * nh * hd_meta:
                # Qwen3.5 packs query and gate inside each head, not in
                # separate contiguous halves of the entire Q projection.
                paired = q.reshape(nh, 2, hd_meta)
                query_gate = paired[:, 1, :].reshape(-1).copy()
                q = paired[:, 0, :].reshape(-1).copy()
        else:
            hd = hd_meta or max(1, qkv.size // (nh + 2 * nk))
            vd = int(self._meta(f"{self.architecture}.attention.value_length", self._meta("attention.value_length", hd)))
            qn, kn = nh * hd, nk * hd
            if qkv.size < qn + kn + nk * vd:
                raise ResidentQwenError("QKV projection is narrower than declared GQA dimensions")
            q, k, v = qkv[:qn], qkv[qn:qn + kn], qkv[qn + kn:qn + kn + nk * vd]
        hd = q.size // nh
        vd = v.size // nk
        if q.size != nh * hd or k.size != nk * hd or v.size != nk * vd or nh % nk:
            raise ResidentQwenError("Qwen full-attention projection shapes are inconsistent")
        if request is not None and graph_capture is not None:
            site = request.get("graph_site")
            if isinstance(site, Mapping) and site.get("specialist") == "attention-memory":
                binding, native_state, successor_shapes = self._attention_memory_site(
                    request, arrays, y, q, k, v, layer,
                )
                if binding is not None:
                    graph_capture.update({
                        "binding": binding, "attn_input": y.copy(),
                        "native_state_applicability": native_state,
                        "successor_shapes": successor_shapes,
                        "native_projection": (q.copy(), k.copy(), v.copy()),
                        "native_projection_ops": 1 if qkv is not None else 3,
                    })
        qnorm = self._vec("attn_q_norm", layer, required=False); knorm = self._vec("attn_k_norm", layer, required=False)
        qh, kh, vh = q.reshape(nh, hd), k.reshape(nk, hd), v.reshape(nk, vd)
        if qnorm is not None:
            if qnorm.size != hd: raise ResidentQwenError("Q norm width mismatch")
            qh = qh / np.sqrt(np.mean(qh * qh, axis=1, keepdims=True) + 1e-6) * qnorm
        if knorm is not None:
            if knorm.size != hd: raise ResidentQwenError("K norm width mismatch")
            kh = kh / np.sqrt(np.mean(kh * kh, axis=1, keepdims=True) + 1e-6) * knorm
        qh = self._exchange("attention.q", qh, layer=layer)
        kh = self._exchange("attention.k", kh, layer=layer)
        vh = self._exchange("attention.v", vh, layer=layer)
        sections = self._meta(f"{self.architecture}.rope.dimension_sections", self._meta("rope.dimension_sections", [hd]))
        base = float(self._meta(f"{self.architecture}.rope.freq_base", self._meta("rope.freq_base", 10000.0)))
        qh = np.stack([self._rope(a, position, sections, base) for a in qh])
        kh = np.stack([self._rope(a, position, sections, base) for a in kh])
        qh = self._exchange("attention.rope-q", qh, layer=layer)
        kh = self._exchange("attention.rope-k", kh, layer=layer)
        key_name, val_name = f"kv_k.{layer}", f"kv_v.{layer}"
        old_k = arrays.get(key_name, np.empty((0, nk, hd), dtype=np.float32)).reshape(-1, nk, hd)
        old_v = arrays.get(val_name, np.empty((0, nk, vd), dtype=np.float32)).reshape(-1, nk, vd)
        keys = self._exchange(
            "attention.key-cache",
            np.concatenate([old_k, kh[None, :, :]], axis=0),
            layer=layer,
        )
        vals = self._exchange(
            "attention.value-cache",
            np.concatenate([old_v, vh[None, :, :]], axis=0),
            layer=layer,
        )
        context = np.empty((nh, vd), dtype=np.float32)
        scale = 1.0 / math.sqrt(float(hd))
        for h in range(nh):
            kv_head = h // (nh // nk)
            scores = (keys[:, kv_head, :] @ qh[h]) * scale
            scores = self._exchange(
                "attention.scores",
                scores,
                layer=layer,
                head=h,
            )
            probabilities = self._exchange(
                "attention.probabilities",
                _softmax(scores),
                layer=layer,
                head=h,
            )
            if np.any(probabilities < 0) or not np.isclose(
                np.sum(probabilities, dtype=np.float32),
                np.float32(1.0),
            ):
                probabilities = np.maximum(
                    probabilities,
                    np.float32(0.0),
                )
                total = np.sum(probabilities, dtype=np.float32)
                if total <= 0:
                    raise ResidentQwenError(
                        "field-modulated attention probabilities have no support"
                    )
                probabilities = probabilities / total
            context[h] = probabilities @ vals[:, kv_head, :]
        context = self._exchange("attention.context", context, layer=layer)
        gate = (
            query_gate
            if query_gate is not None
            else self._mat("attn_gate", y, layer, required=False)
        )
        flat = context.reshape(-1)
        if gate is not None:
            gate = self._exchange("attention.gate", gate, layer=layer)
            gate_activation = self._exchange(
                "attention.gate-activation",
                np.asarray(_sigmoid(gate), dtype=np.float32),
                layer=layer,
            )
            if gate_activation.size == flat.size:
                flat = flat * gate_activation
            elif gate_activation.size == nh * hd:
                flat = flat * gate_activation.repeat(max(1, vd // hd))
        flat = self._exchange(
            "attention.gated-context",
            flat,
            layer=layer,
        )
        out = self._mat("attn_out", flat, layer)
        if out is None:
            raise ResidentQwenError("full-attention output projection is absent")
        out = self._exchange("attention.projected", out, layer=layer)
        arrays[key_name], arrays[val_name] = keys, vals
        return out

    def _full_attention_device(
        self,
        x: Any,
        arrays: dict[str, np.ndarray],
        layer: int,
        position: int | Sequence[int],
    ) -> tuple[Any, Any, Any, int, int, int]:
        """Keep the grouped-query attention path and field sites on Vulkan."""
        epoch = self._device_epoch
        norm_name = self._weight("attn_norm", layer)
        assert norm_name is not None
        y = self._exchange_device(
            "attention.normalized",
            epoch.norm_rows(
                x, row_width=x.count,
                epsilon=float(self._meta(f"{self.architecture}.attention.layer_norm_rms_epsilon", 1e-6)),
                sum_squares=False, weight_name=norm_name,
            ),
            layer=layer,
        )
        nh = int(self._meta(f"{self.architecture}.attention.head_count", self._meta("attention.head_count", 1)))
        nk = int(self._meta(f"{self.architecture}.attention.head_count_kv", self._meta("attention.head_count_kv", nh)))
        hd_meta = int(self._meta(f"{self.architecture}.attention.key_length", self._meta("attention.key_length", 0)))
        gate = None
        def join_heads(heads: list[Any]) -> Any:
            result = heads[0]
            for item in heads[1:]:
                result = epoch.concat(result, item)
            return result
        qkv_name = self._weight("attn_qkv", layer, required=False)
        if qkv_name is None:
            names = tuple(self._weight(stem, layer) for stem in ("attn_q", "attn_k", "attn_v"))
            q, k, v = epoch.matvec_many(names, y)
            if hd_meta > 0 and q.count == 2 * nh * hd_meta:
                packed = q
                q = join_heads([
                    epoch.view(packed, head * 2 * hd_meta, hd_meta)
                    for head in range(nh)
                ])
                gate = join_heads([
                    epoch.view(packed, (head * 2 + 1) * hd_meta, hd_meta)
                    for head in range(nh)
                ])
        else:
            combined = epoch.matvec(qkv_name, y)
            hd = hd_meta or max(1, combined.count // (nh + 2 * nk))
            vd = int(self._meta(f"{self.architecture}.attention.value_length", self._meta("attention.value_length", hd)))
            qn, kn = nh * hd, nk * hd
            if combined.count < qn + kn + nk * vd:
                raise ResidentQwenError("QKV projection is narrower than declared GQA dimensions")
            q = epoch.view(combined, 0, qn)
            k = epoch.view(combined, qn, kn)
            v = epoch.view(combined, qn + kn, nk * vd)
        hd = q.count // nh
        vd = v.count // nk
        if q.count != nh * hd or k.count != nk * hd or v.count != nk * vd or nh % nk:
            raise ResidentQwenError("Qwen full-attention projection shapes are inconsistent")
        qnorm = self._weight("attn_q_norm", layer, required=False)
        knorm = self._weight("attn_k_norm", layer, required=False)
        if qnorm is not None:
            q = epoch.norm_rows(q, row_width=hd, epsilon=1e-6,
                                sum_squares=False, weight_name=qnorm)
        if knorm is not None:
            k = epoch.norm_rows(k, row_width=hd, epsilon=1e-6,
                                sum_squares=False, weight_name=knorm)
        q = self._exchange_device("attention.q", q, layer=layer)
        k = self._exchange_device("attention.k", k, layer=layer)
        v = self._exchange_device("attention.v", v, layer=layer)
        sections = self._meta(
            f"{self.architecture}.rope.dimension_sections",
            self._meta("rope.dimension_sections", [hd]),
        )
        base = float(self._meta(f"{self.architecture}.rope.freq_base", self._meta("rope.freq_base", 10000.0)))
        n_rot = self._rope_dimension_count(hd)
        if self._is_imrope_sections(sections, n_rot):
            q_host, k_host = epoch.download_many([q, k])
            q_host = q_host.reshape(nh, hd)
            k_host = k_host.reshape(nk, hd)
            q_rotated = np.empty_like(q_host)
            k_rotated = np.empty_like(k_host)
            for head in range(nh):
                q_rotated[head] = self._rope(q_host[head], position, sections, base)
            for head in range(nk):
                k_rotated[head] = self._rope(k_host[head], position, sections, base)
            q_heads = [epoch.upload(q_rotated.reshape(-1))]
            k_heads = [epoch.upload(k_rotated.reshape(-1))]
        else:
            q_heads = [
                epoch.rope(epoch.view(q, head * hd, hd), position, sections, base)
                for head in range(nh)
            ]
            k_heads = [
                epoch.rope(epoch.view(k, head * hd, hd), position, sections, base)
                for head in range(nk)
            ]
        q = self._exchange_device("attention.rope-q", join_heads(q_heads), layer=layer)
        k = self._exchange_device("attention.rope-k", join_heads(k_heads), layer=layer)
        key_name, val_name = f"kv_k.{layer}", f"kv_v.{layer}"
        old_k = arrays.get(key_name)
        old_v = arrays.get(val_name)
        keys = epoch.concat(epoch.upload(old_k.reshape(-1)), k) if old_k is not None and old_k.size else k
        vals = epoch.concat(epoch.upload(old_v.reshape(-1)), v) if old_v is not None and old_v.size else v
        keys = self._exchange_device("attention.key-cache", keys, layer=layer)
        vals = self._exchange_device("attention.value-cache", vals, layer=layer)
        context_heads = []
        for head in range(nh):
            kv_head = head // (nh // nk)
            scores = epoch.attention_scores(
                epoch.view(q, head * hd, hd), keys, kv_head, nk, hd,
                1.0 / math.sqrt(float(hd)),
            )
            scores = self._device_membrane.device_exchange(
                self._neural_site("attention.scores", layer=layer, head=head), scores,
            )
            probabilities = self._device_membrane.device_exchange(
                self._neural_site("attention.probabilities", layer=layer, head=head),
                epoch.softmax(scores),
            )
            probabilities = epoch.positive_normalize(probabilities)
            context_heads.append(
                epoch.attention_context(probabilities, vals, kv_head, nk, vd)
            )
        context = self._exchange_device(
            "attention.context", join_heads(context_heads), layer=layer,
        )
        if gate is None:
            gate_name = self._weight("attn_gate", layer, required=False)
            gate = epoch.matvec(gate_name, y) if gate_name is not None else None
        flat = context
        if gate is not None:
            gate = self._exchange_device("attention.gate", gate, layer=layer)
            active = self._exchange_device(
                "attention.gate-activation", epoch.sigmoid(gate), layer=layer,
            )
            if active.count != flat.count:
                raise ResidentQwenError("full-attention query gate width is unsupported")
            flat = epoch.mul(flat, active)
        flat = self._exchange_device("attention.gated-context", flat, layer=layer)
        out_name = self._weight("attn_out", layer)
        assert out_name is not None
        projected = self._exchange_device(
            "attention.projected", epoch.matvec(out_name, flat), layer=layer,
        )
        return projected, keys, vals, nk, hd, vd

    def _recurrent_attention(
        self, x: np.ndarray, arrays: dict[str, np.ndarray], layer: int, position: int,
        request: Mapping[str, Any] | None = None,
        graph_capture: dict[str, Any] | None = None,
        normalized: np.ndarray | None = None,
    ) -> np.ndarray:
        """Run one Qwen3.5 gated-delta recurrent attention token."""
        y = normalized if normalized is not None else self._exchange(
            "attention.normalized", self._norm(x, "attn_norm", layer), layer=layer,
        )
        graph_binding = graph_method = graph_state = graph_shapes = None
        graph_features = graph_cost = graph_proposal = None
        graph_refusal = None
        if request is not None and graph_capture is not None:
            (graph_binding, graph_method, graph_state, graph_shapes,
             graph_features, graph_cost) = self._recurrent_graph_site(
                request, arrays, y, layer,
            )
        graph_verb = (
            request.get("graph_site", {}).get("verb")
            if isinstance(request, Mapping) and isinstance(request.get("graph_site"), Mapping)
            else None
        )
        shadow_history = f"graph_native_conv_history.{layer}"
        shadow_state = f"graph_native_recurrent_state.{layer}"
        shadow_position = f"graph_native_position.{layer}"
        arrays.pop(shadow_history, None)
        arrays.pop(shadow_state, None)
        arrays.pop(shadow_position, None)
        selections = (
            graph_method if isinstance(graph_method, list)
            else [graph_method] if graph_method is not None else []
        )
        if selections and graph_verb not in {"replace", "propose"}:
            graph_refusal = "recurrent successor methods support replacement or proposal only"
        elif selections and (self._activation_exchange is not None or self._device_membrane is not None):
            graph_refusal = "recurrent graph-site intervention cannot skip an active field exchange"
        elif selections and graph_features is not None and graph_shapes is not None:
            hidden_width = int(graph_shapes["hidden"]["shape"][0])
            history_name = f"conv_history.{layer}"
            state_name = f"recurrent_state.{layer}"
            history_shape = tuple(int(dim) for dim in graph_shapes[history_name]["shape"])
            state_shape = tuple(int(dim) for dim in graph_shapes[state_name]["shape"])
            history_width = int(np.prod(history_shape, dtype=np.int64))
            state_width = int(np.prod(state_shape, dtype=np.int64))
            output_width = hidden_width + history_width + state_width
            for selected in selections:
                try:
                    predicted = self._graph_site_result(
                        selected["method"], graph_features, output_width,
                        selected["method_key"], "recurrent_features", "recurrent_successor",
                    )
                    if self._device_epoch is not None:
                        predicted = self._device_epoch.download(predicted)
                    successor = _finite_array(
                        predicted, name="recurrent successor",
                    ).reshape(-1)
                    if successor.size != output_width:
                        raise ResidentQwenError("recurrent successor width is invalid")
                    if graph_verb == "propose":
                        rank = int(selected["method"]["rank"])
                        graph_proposal = {
                            "method_key": selected["method_key"],
                            "method_generation": selected["method_generation"],
                            "candidate_output_sha256": _graph_f32_payload(successor)["sha256"],
                            "added_flops": int(2 * (
                                graph_features.size * rank + rank * output_width
                            ) + output_width),
                        }
                        break
                    arrays[history_name] = successor[
                        hidden_width:hidden_width + history_width
                    ].reshape(history_shape)
                    arrays[state_name] = successor[
                        hidden_width + history_width:
                    ].reshape(state_shape)
                    if graph_capture is not None and graph_binding is not None:
                        graph_capture.update({
                            "binding": graph_binding,
                            "recurrent_features": graph_features.copy(),
                            "native_state_applicability": graph_state,
                            "successor_shapes": graph_shapes,
                            "potential_cost": graph_cost,
                            "replaced": True,
                            "method_key": selected["method_key"],
                            "method_generation": selected["method_generation"],
                            "refusal": None,
                        })
                    return successor[:hidden_width].copy()
                except (ResidentQwenError, KeyError, ValueError) as exc:
                    graph_refusal = str(exc)
        graph_method = None
        qkv_mixed, z_gate = self._mat_many(
            (("attn_qkv", None), ("attn_gate", None)), y, layer,
        )
        if qkv_mixed is None or z_gate is None:
            raise ResidentQwenError("recurrent QKV and z-gate projections are required")
        nk = int(self._meta(f"{self.architecture}.ssm.group_count", self._meta("ssm.group_count", 1)))
        key_dim = int(self._meta(f"{self.architecture}.ssm.state_size", self._meta("ssm.state_size", 1)))
        inner = int(self._meta(f"{self.architecture}.ssm.inner_size", self._meta("ssm.inner_size", 0)))
        nv = int(self._meta(f"{self.architecture}.ssm.time_step_rank", self._meta("ssm.time_step_rank", 0))) or nk
        if nv < nk or nv % nk:
            raise ResidentQwenError("Qwen recurrent value heads must be a multiple of key heads")
        value_dim = max(1, inner // nv) if inner else key_dim
        qn, vn = nk * key_dim, nv * value_dim
        if qkv_mixed.size != qn * 2 + vn:
            raise ResidentQwenError("recurrent QKV projection shape does not match source qkv_dim")
        history_name = f"conv_history.{layer}"
        raw_qkv = self._exchange(
            "recurrent.raw-qkv",
            qkv_mixed.astype(np.float32, copy=True),
            layer=layer,
        )
        history_rows = self._conv_history_rows(layer, raw_qkv.size)
        next_history = self._exchange(
            "recurrent.conv-history",
            np.concatenate([
                _conv_window(arrays.get(history_name), history_rows, raw_qkv.size),
                raw_qkv[None, :],
            ], axis=0),
            layer=layer,
        )
        conv_name = self._weight("ssm_conv1d", layer, required=False)
        convolved = next_history[-1]
        if conv_name is not None:
            kernel = self._tensor(conv_name).reshape(raw_qkv.size, -1)
            kernel_size = kernel.shape[1]
            taps = next_history[-kernel_size:]
            # GGML's causal window aligns the current sample with the final
            # kernel coefficient; rows before the first token are zero.
            convolved = np.sum(
                taps * kernel.T[kernel_size - taps.shape[0]:],
                axis=0,
                dtype=np.float32,
            )
        arrays[history_name] = next_history[next_history.shape[0] - history_rows:].copy()
        qkv_mixed = self._exchange(
            "recurrent.convolved-qkv",
            _silu(convolved),
            layer=layer,
        )
        q = qkv_mixed[:qn].reshape(nk, key_dim)
        k = qkv_mixed[qn:2 * qn].reshape(nk, key_dim)
        v = qkv_mixed[2 * qn:2 * qn + vn].reshape(nv, value_dim)
        eps = float(self._meta(f"{self.architecture}.attention.layer_norm_rms_epsilon", self._meta("attention.layer_norm_epsilon", 1e-6)))
        q = q / np.sqrt(np.sum(q * q, axis=1, keepdims=True) + eps)
        k = k / np.sqrt(np.sum(k * k, axis=1, keepdims=True) + eps)
        q = self._exchange("recurrent.q", q, layer=layer)
        k = self._exchange("recurrent.k", k, layer=layer)
        v = self._exchange("recurrent.v", v, layer=layer)
        state_name = f"recurrent_state.{layer}"
        state = arrays.get(state_name, np.zeros((nv, value_dim, key_dim), dtype=np.float32)).reshape(nv, value_dim, key_dim).copy()
        beta, alpha = self._mat_many(
            (("ssm_beta", None), ("ssm_alpha", None)),
            y,
            layer,
            required=False,
        )
        beta_h = np.asarray(_sigmoid(beta[:nv] if beta is not None and beta.size >= nv else np.zeros(nv, dtype=np.float32)), dtype=np.float32)
        beta_h = self._exchange("recurrent.beta", beta_h, layer=layer)
        dt = self._vec("ssm_dt", layer, required=False)
        a_log = self._vec("ssm_a", layer, required=False)
        alpha_h = alpha[:nv] if alpha is not None and alpha.size >= nv else np.zeros(nv, dtype=np.float32)
        if dt is not None:
            if dt.size < nv: raise ResidentQwenError("ssm_dt width is smaller than value head count")
            alpha_h = alpha_h + dt[:nv]
        alpha_h = self._exchange("recurrent.alpha", alpha_h, layer=layer)
        gate_h = np.log1p(np.exp(-np.abs(alpha_h))) + np.maximum(alpha_h, 0.0)
        if a_log is not None:
            if a_log.size < nv: raise ResidentQwenError("ssm_a width is smaller than value head count")
            gate_h = gate_h * a_log[:nv]
        gate_h = self._exchange("recurrent.decay", gate_h, layer=layer)
        predictions = np.empty((nv, value_dim), dtype=np.float32)
        for h in range(nv):
            state[h] *= np.float32(
                math.exp(float(np.clip(gate_h[h], -80.0, 80.0)))
            )
        state = self._exchange(
            "recurrent.decayed-state",
            state,
            layer=layer,
        )
        for h in range(nv):
            predictions[h] = state[h] @ k[h % nk]
        predictions = self._exchange(
            "recurrent.prediction",
            predictions,
            layer=layer,
        )
        deltas = np.empty((nv, value_dim), dtype=np.float32)
        for h in range(nv):
            deltas[h] = (v[h] - predictions[h]) * beta_h[h]
        deltas = self._exchange("recurrent.delta", deltas, layer=layer)
        for h in range(nv):
            state[h] += np.outer(deltas[h], k[h % nk])
        state = self._exchange("recurrent.state", state, layer=layer)
        out = np.empty((nv, value_dim), dtype=np.float32)
        for h in range(nv):
            out[h] = (state[h] @ q[h % nk]) * np.float32(1.0 / math.sqrt(value_dim))
        out = self._exchange("recurrent.readout", out, layer=layer)
        arrays[state_name] = state
        norm = self._vec("ssm_norm", layer, required=False)
        if norm is not None:
            if norm.size != value_dim:
                raise ResidentQwenError("ssm_norm width mismatch")
            out = (
                out
                / np.sqrt(
                    np.mean(out * out, axis=1, keepdims=True) + eps
                )
                * norm
            )
        out = self._exchange("recurrent.normalized", out, layer=layer)
        zg = z_gate[:nv * value_dim]
        if zg.size != nv * value_dim:
            raise ResidentQwenError(
                "recurrent z-gate width does not match value heads"
            )
        zg = self._exchange(
            "recurrent.z-gate",
            zg.reshape(nv, value_dim),
            layer=layer,
        )
        zg = self._exchange(
            "recurrent.z-activation",
            _silu(zg),
            layer=layer,
        )
        out = self._exchange(
            "recurrent.gated-output",
            out * zg,
            layer=layer,
        )
        readout_input = out.reshape(-1)
        proj = self._mat("ssm_out", readout_input, layer, required=False)
        if proj is None:
            proj = self._mat("attn_out", readout_input, layer)
        assert proj is not None
        projected = self._exchange("recurrent.projected", proj, layer=layer)
        if graph_capture is not None and graph_binding is not None:
            graph_capture.update({
                "binding": graph_binding,
                "recurrent_features": graph_features.copy() if graph_features is not None else None,
                "native_state_applicability": graph_state,
                "successor_shapes": graph_shapes,
                "potential_cost": graph_cost,
                "replaced": False,
                "method_key": graph_proposal["method_key"] if graph_proposal else None,
                "method_generation": (
                    graph_proposal["method_generation"] if graph_proposal else None
                ),
                "refusal": graph_refusal,
                **({"proposal": graph_proposal} if graph_proposal is not None else {}),
            })
        return projected

    def _recurrent_attention_device(
        self,
        x: Any,
        arrays: dict[str, np.ndarray],
        layer: int,
    ) -> tuple[Any, Any, Any, int, int, int]:
        """Keep one recurrent attention layer and its field sites on Vulkan."""
        epoch = self._device_epoch
        norm_name = self._weight("attn_norm", layer)
        assert norm_name is not None
        y = self._exchange_device(
            "attention.normalized",
            epoch.norm_rows(
                x, row_width=x.count, epsilon=1e-6,
                sum_squares=False, weight_name=norm_name,
            ),
            layer=layer,
        )
        qkv_name = self._weight("attn_qkv", layer)
        gate_name = self._weight("attn_gate", layer)
        assert qkv_name is not None and gate_name is not None
        qkv, z_gate = epoch.matvec_many((qkv_name, gate_name), y)
        nk = int(self._meta(f"{self.architecture}.ssm.group_count", self._meta("ssm.group_count", 1)))
        key_dim = int(self._meta(f"{self.architecture}.ssm.state_size", self._meta("ssm.state_size", 1)))
        inner = int(self._meta(f"{self.architecture}.ssm.inner_size", self._meta("ssm.inner_size", 0)))
        nv = int(self._meta(f"{self.architecture}.ssm.time_step_rank", self._meta("ssm.time_step_rank", 0))) or nk
        if nv < nk or nv % nk:
            raise ResidentQwenError("Qwen recurrent value heads must be a multiple of key heads")
        value_dim = max(1, inner // nv) if inner else key_dim
        qn, vn = nk * key_dim, nv * value_dim
        if qkv.count != 2 * qn + vn:
            raise ResidentQwenError("recurrent QKV projection shape does not match source qkv_dim")
        raw = self._exchange_device("recurrent.raw-qkv", qkv, layer=layer)
        history_rows = self._conv_history_rows(layer, qkv.count)
        history = (
            epoch.concat(epoch.upload(_conv_window(
                arrays.get(f"conv_history.{layer}"), history_rows, qkv.count,
            ).reshape(-1)), raw)
            if history_rows else raw
        )
        history = self._exchange_device("recurrent.conv-history", history, layer=layer)
        conv_name = self._weight("ssm_conv1d", layer, required=False)
        convolved = (
            epoch.recurrent_conv(history, conv_name, channels=qkv.count)
            if conv_name is not None
            else epoch.view(history, history.count - qkv.count, qkv.count)
        )
        convolved = self._exchange_device(
            "recurrent.convolved-qkv", epoch.silu(convolved), layer=layer,
        )
        eps = float(self._meta(
            f"{self.architecture}.attention.layer_norm_rms_epsilon",
            self._meta("attention.layer_norm_epsilon", 1e-6),
        ))
        q = epoch.norm_rows(epoch.view(convolved, 0, qn), row_width=key_dim,
                            epsilon=eps, sum_squares=True)
        k = epoch.norm_rows(epoch.view(convolved, qn, qn), row_width=key_dim,
                            epsilon=eps, sum_squares=True)
        v = epoch.view(convolved, 2 * qn, vn)
        q = self._exchange_device("recurrent.q", q, layer=layer)
        k = self._exchange_device("recurrent.k", k, layer=layer)
        v = self._exchange_device("recurrent.v", v, layer=layer)
        previous_state = arrays.get(f"recurrent_state.{layer}")
        state = epoch.upload(
            previous_state.reshape(-1) if previous_state is not None
            else np.zeros(nv * value_dim * key_dim, dtype=np.float32)
        )
        beta_name = self._weight("ssm_beta", layer, required=False)
        alpha_name = self._weight("ssm_alpha", layer, required=False)
        beta = epoch.matvec(beta_name, y) if beta_name is not None else epoch.upload(np.zeros(nv, dtype=np.float32))
        alpha = epoch.matvec(alpha_name, y) if alpha_name is not None else epoch.upload(np.zeros(nv, dtype=np.float32))
        if beta.count < nv or alpha.count < nv:
            raise ResidentQwenError("recurrent beta/alpha width is smaller than value head count")
        beta_h = self._exchange_device(
            "recurrent.beta", epoch.sigmoid(epoch.view(beta, 0, nv)), layer=layer,
        )
        alpha_h = epoch.view(alpha, 0, nv)
        dt = self._vec("ssm_dt", layer, required=False)
        if dt is not None:
            if dt.size < nv:
                raise ResidentQwenError("ssm_dt width is smaller than value head count")
            alpha_h = epoch.add(alpha_h, epoch.upload(dt[:nv]))
        alpha_h = self._exchange_device("recurrent.alpha", alpha_h, layer=layer)
        gate = epoch.softplus(alpha_h)
        a_log = self._vec("ssm_a", layer, required=False)
        if a_log is not None:
            if a_log.size < nv:
                raise ResidentQwenError("ssm_a width is smaller than value head count")
            gate = epoch.mul(gate, epoch.upload(a_log[:nv]))
        gate = self._exchange_device("recurrent.decay", gate, layer=layer)
        state = epoch.mul_rows(
            state, epoch.exp_clipped(gate, -80.0, 80.0),
            row_width=value_dim * key_dim,
        )
        state = self._exchange_device("recurrent.decayed-state", state, layer=layer)
        prediction = self._exchange_device(
            "recurrent.prediction",
            epoch.recurrent_predict(state, k, nv, nk, value_dim, key_dim),
            layer=layer,
        )
        delta = epoch.mul_rows(
            epoch.add(v, epoch.scale(prediction, -1.0)), beta_h,
            row_width=value_dim,
        )
        delta = self._exchange_device("recurrent.delta", delta, layer=layer)
        state = self._exchange_device(
            "recurrent.state",
            epoch.recurrent_update(state, k, delta, nv, nk, value_dim, key_dim),
            layer=layer,
        )
        out = self._exchange_device(
            "recurrent.readout",
            epoch.scale(
                epoch.recurrent_readout(state, q, nv, nk, value_dim, key_dim),
                1.0 / math.sqrt(value_dim),
            ),
            layer=layer,
        )
        ssm_norm = self._weight("ssm_norm", layer, required=False)
        if ssm_norm is not None:
            out = epoch.norm_rows(
                out, row_width=value_dim, epsilon=eps,
                sum_squares=False, weight_name=ssm_norm,
            )
        out = self._exchange_device("recurrent.normalized", out, layer=layer)
        if z_gate.count < vn:
            raise ResidentQwenError("recurrent z-gate width does not match value heads")
        zg = self._exchange_device("recurrent.z-gate", epoch.view(z_gate, 0, vn), layer=layer)
        zg = self._exchange_device("recurrent.z-activation", epoch.silu(zg), layer=layer)
        out = self._exchange_device("recurrent.gated-output", epoch.mul(out, zg), layer=layer)
        proj_name = self._weight("ssm_out", layer, required=False)
        if proj_name is None:
            proj_name = self._weight("attn_out", layer)
        assert proj_name is not None
        projected = self._exchange_device(
            "recurrent.projected", epoch.matvec(proj_name, out), layer=layer,
        )
        return projected, history, state, qkv.count, value_dim, key_dim

    def _attention(
        self,
        request: Mapping[str, Any],
        arrays: dict[str, np.ndarray],
        *,
        persist: bool = True,
        graph_capture: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
        layer = int(request["layer"])
        position = int(request["position"])
        parameters = request.get("parameters")
        raw_rope_axes = (
            parameters.get("rope_position_ids")
            if isinstance(parameters, Mapping)
            else None
        )
        is_visual_token = (
            isinstance(parameters, Mapping)
            and "visual_embedding_index" in parameters
        )
        if is_visual_token and raw_rope_axes is None:
            raise ResidentQwenError(
                "visual image token is missing its spatial M-RoPE positions"
            )
        rope_position: int | Sequence[int] = position
        if raw_rope_axes is not None:
            if (
                not isinstance(raw_rope_axes, Sequence)
                or isinstance(raw_rope_axes, (str, bytes))
                or len(raw_rope_axes) != 4
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                    for value in raw_rope_axes
                )
            ):
                raise ResidentQwenError(
                    "M-RoPE positions must be four nonnegative axes"
                )
            rope_position = tuple(int(value) for value in raw_rope_axes)
        x = arrays.get("hidden")
        arrays.pop("router_ids", None)
        arrays.pop("router_weights", None)
        if x is None:
            raise ResidentQwenError("attention stage requires hidden in snapshot")
        interval = int(self._meta(f"{self.architecture}.full_attention_interval", self._meta("full_attention_interval", 4)))
        recurrent = bool((request.get("parameters") or {}).get("recurrent", interval > 0 and (layer + 1) % interval != 0))
        if (self._device_epoch is not None
                and not (recurrent and graph_capture is not None
                         and isinstance(request.get("graph_site"), Mapping)
                         and request["graph_site"].get("specialist") == "recurrent-dynamics")):
            epoch = self._device_epoch
            device_x = self._exchange_device(
                "attention.input", epoch.upload(x.reshape(-1)), layer=layer,
            )
            if recurrent:
                out, history, state, channel_count, value_dim, key_dim = (
                    self._recurrent_attention_device(device_x, arrays, layer)
                )
                history_host, state_host = epoch.download_many([history, state])
                nv = state_host.size // (value_dim * key_dim)
                arrays[f"conv_history.{layer}"] = history_host.reshape(-1, channel_count)[1:]
                arrays[f"recurrent_state.{layer}"] = state_host.reshape(nv, value_dim, key_dim)
            else:
                out, keys, vals, nk, head_dim, value_dim = (
                    self._full_attention_device(
                        device_x, arrays, layer, rope_position
                    )
                )
                key_host, value_host = epoch.download_many([keys, vals])
                arrays[f"kv_k.{layer}"] = key_host.reshape(-1, nk, head_dim)
                arrays[f"kv_v.{layer}"] = value_host.reshape(-1, nk, value_dim)
            if not persist and self.architecture == "qwen35":
                arrays["_device_attention_residual"] = device_x
                arrays["_device_hidden"] = out
                return arrays, {}
            residual_host, hidden_host = epoch.download_many([device_x, out])
            arrays["attention_residual"] = residual_host
            arrays["hidden"] = hidden_host
            return arrays, self._save_state(arrays, request) if persist else {}
        x = self._exchange("attention.input", x.reshape(-1), layer=layer)
        if recurrent:
            out = self._recurrent_attention(x, arrays, layer, position, request, graph_capture)
        else:
            out = self._full_attention(
                x, arrays, layer, rope_position, request, graph_capture,
            )
        arrays["attention_residual"] = x.copy()
        arrays["hidden"] = np.asarray(out, dtype=np.float32)
        if graph_capture is not None and graph_capture.get("binding") is not None:
            if graph_capture["binding"].get("specialist") == "recurrent-dynamics":
                graph_capture["successor_state"] = {
                    "hidden": _graph_state_descriptor(arrays["hidden"]),
                    f"conv_history.{layer}": _graph_state_descriptor(arrays[f"conv_history.{layer}"]),
                    f"recurrent_state.{layer}": _graph_state_descriptor(arrays[f"recurrent_state.{layer}"]),
                }
                graph_capture["successor_vector"] = np.concatenate((
                    arrays["hidden"].reshape(-1),
                    arrays[f"conv_history.{layer}"].reshape(-1),
                    arrays[f"recurrent_state.{layer}"].reshape(-1),
                )).astype(np.float32, copy=False)
            else:
                graph_capture["successor_state"] = {
                    "hidden": _graph_state_descriptor(arrays["hidden"]),
                    f"kv_k.{layer}": _graph_state_descriptor(arrays[f"kv_k.{layer}"]),
                    f"kv_v.{layer}": _graph_state_descriptor(arrays[f"kv_v.{layer}"]),
                }
        return arrays, self._save_state(arrays, request) if persist else {}
    def _dense_ffn_device(
        self,
        x: Any,
        attention_residual: Any | None,
        layer: int,
    ) -> np.ndarray:
        epoch = self._device_epoch
        base = x if attention_residual is None else epoch.add(attention_residual, x)
        residual = self._exchange_device("ffn.residual", base, layer=layer)
        norm_name = self._weight("ffn_norm", layer)
        assert norm_name is not None
        normalized = epoch.norm_rows(
            residual, row_width=residual.count, epsilon=1e-6,
            sum_squares=False, weight_name=norm_name,
        )
        y = self._exchange_device("ffn.normalized", normalized, layer=layer)
        gate_name = self._weight("ffn_gate", layer)
        up_name = self._weight("ffn_up", layer)
        down_name = self._weight("ffn_down", layer)
        assert gate_name is not None and up_name is not None and down_name is not None
        gate, up = epoch.matvec_many((gate_name, up_name), y)
        gate = self._exchange_device("ffn.dense-gate", gate, layer=layer)
        up = self._exchange_device("ffn.dense-up", up, layer=layer)
        activated = self._exchange_device(
            "ffn.dense-silu", epoch.mul(epoch.silu(gate), up), layer=layer,
        )
        down = self._exchange_device(
            "ffn.dense-down", epoch.matvec(down_name, activated), layer=layer,
        )
        output = self._exchange_device("ffn.output", down, layer=layer)
        hidden = self._exchange_device(
            "layer.output", epoch.add(residual, output), layer=layer,
        )
        return epoch.download(hidden)

    def _expert_graph_cost(
        self, layer: int, expert_ids: Sequence[int], expert_count: int,
    ) -> dict[str, Any]:
        gate_name = self._weight("ffn_gate_exps", layer, required=False)
        up_name = self._weight("ffn_up_exps", layer, required=False)
        packed_name = self._weight("ffn_gate_up_exps", layer, required=False)
        down_name = self._weight("ffn_down_exps", layer, required=False)
        packed = gate_name is None or up_name is None
        if packed:
            routed_names = (packed_name, down_name)
        else:
            routed_names = (gate_name, up_name, down_name)
        if (expert_count <= 0 or not expert_ids or any(name is None for name in routed_names)):
            raise ResidentQwenError("expert graph site has incomplete routed tensors")

        def matrix_flops(name: str, experts: int = 1) -> int:
            descriptor = self._tensor_shapes.get(name)
            shape = descriptor.get("shape") if isinstance(descriptor, Mapping) else None
            if (not isinstance(shape, (list, tuple)) or not shape
                    or any(isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0 for dim in shape)):
                raise ResidentQwenError("expert graph tensor shape is invalid")
            elements = math.prod(shape)
            if experts > 1:
                if elements % experts:
                    raise ResidentQwenError("expert graph tensor shape disagrees with expert count")
                elements //= experts
            return 2 * int(elements)

        omitted_ops = []
        routed_flops = 0
        for expert in expert_ids:
            if packed:
                omitted_ops.extend((
                    f"ffn_gate_up_exps[{expert}]", f"ffn_down_exps[{expert}]",
                ))
            else:
                omitted_ops.extend((
                    f"ffn_gate_exps[{expert}]", f"ffn_up_exps[{expert}]",
                    f"ffn_down_exps[{expert}]",
                ))
            routed_flops += sum(
                matrix_flops(name, expert_count) for name in routed_names if name is not None
            )
        shared_prefix = (
            "ffn_gate_inp_shexp", "ffn_gate_shexp", "ffn_up_shexp",
        )
        shared_names = tuple(self._weight(name, layer, required=False) for name in shared_prefix)
        shared_down = self._weight("ffn_down_shexp", layer, required=False)
        shared = all(name is not None for name in shared_names)
        if shared:
            if shared_down is None:
                raise ResidentQwenError("shared expert graph site has no down projection")
            omitted_ops.extend((*shared_prefix, "ffn_down_shexp"))
            routed_flops += sum(matrix_flops(name) for name in (*shared_names, shared_down) if name is not None)
        return {
            "native_ops_omitted": len(omitted_ops),
            "flops": routed_flops,
            "omitted_ops": omitted_ops,
        }

    def _expert_graph_site(
        self, request: Mapping[str, Any], arrays: Mapping[str, np.ndarray],
        normalized: np.ndarray,
    ) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
        site = request.get("graph_site")
        if site is None or request["stage"] != "qwen-experts":
            return None, None
        if not isinstance(site, Mapping) or site.get("specialist") != "expert-synthesis":
            raise ResidentQwenError("expert graph site is invalid")
        if site.get("source_sha256") != self.source_sha256:
            raise ResidentQwenError("expert graph site has a different model source")
        dependencies = site.get("dependencies")
        if not isinstance(dependencies, Mapping):
            return None, None
        profile = dependencies.get("membrane_profile")
        field_epoch = dependencies.get("field_epoch_sha256")
        native_state = {
            "membrane_profile": _plain(profile),
            "field_epoch_sha256": field_epoch,
        }
        ids = arrays.get("router_ids")
        if ids is None:
            raise ResidentQwenError("expert graph site has no resolved router")
        selected_ids = [int(value) for value in np.asarray(ids).reshape(-1)]
        native_state["expert_route"] = {
            "expert_ids": selected_ids,
            "top_k": len(selected_ids),
        }
        from .graph_site import candidate_for_site, invocation
        binding = invocation(
            source_sha256=self.source_sha256,
            architecture=self.architecture,
            backend=self.backend,
            sequence_id=str(site.get("sequence_id", "")),
            position=int(site.get("position", -1)),
            stage=str(site.get("stage", "")),
            layer=request["layer"],
            site=str(site.get("site", "")),
            specialist="expert-synthesis",
            predecessor_generation=int(site.get("predecessor_generation", -1)),
            predecessor_sha256=str(site.get("predecessor_snapshot_sha256", "")),
            intervention_order=int(site.get("intervention_order", -1)),
            dependencies=site.get("dependencies", {}),
            request_sha256=str(request.get("request_sha256", "")),
            verb=str(site.get("verb", "observe")),
        )
        site_arrays = dict(arrays)
        site_arrays["attn_post_norm"] = np.asarray(normalized, dtype=np.float32).reshape(-1)
        # Bind to the exact field state. Replacement is refused when field
        # exchanges intervene; observation still records the post-field input.
        if self._activation_exchange is not None or self._device_membrane is not None:
            return binding, None
        if site.get("verb") != "replace":
            return binding, None
        provider = self._graph_site_candidate_provider
        metadata = {
            "backend": self.backend,
            "native_state_applicability": native_state,
        }
        if callable(provider):
            selected = provider(request, site_arrays, metadata)
        else:
            policies = request.get("policies")
            graph_state = policies.get("graph_sites") if isinstance(policies, Mapping) else None
            if not isinstance(graph_state, Mapping):
                return binding, None
            selected = candidate_for_site(
                {"source_sha256": self.source_sha256, "graph_sites": graph_state},
                request,
                site_arrays,
                metadata,
            )
        if selected is not None and selected.get("invocation") != binding:
            raise ResidentQwenError("selected expert method has a stale graph-site binding")
        return binding, selected

    def _recurrent_graph_site(
        self, request: Mapping[str, Any], arrays: Mapping[str, np.ndarray],
        normalized: np.ndarray, layer: int,
    ) -> tuple[Mapping[str, Any] | None,
               Mapping[str, Any] | list[Mapping[str, Any]] | None,
               Mapping[str, Any] | None, Mapping[str, Any] | None,
               np.ndarray | None, Mapping[str, int] | None]:
        site = request.get("graph_site")
        if site is None:
            return None, None, None, None, None, None
        from .graph_site import SITE_STAGES
        if (not isinstance(site, Mapping) or site.get("specialist") != "recurrent-dynamics"
                or request.get("stage") != SITE_STAGES.get((self.architecture, "recurrent-dynamics"))
                or request.get("layer") != layer):
            raise ResidentQwenError("recurrent-dynamics graph site is invalid")
        dependencies = site.get("dependencies")
        if not isinstance(dependencies, Mapping):
            return None, None, None, None, None, None

        from .graph_site import candidates_for_site, invocation
        native_state = {
            "membrane_profile": _plain(dependencies.get("membrane_profile")),
            "field_epoch_sha256": dependencies.get("field_epoch_sha256"),
        }
        binding = invocation(
            source_sha256=self.source_sha256, architecture=self.architecture,
            backend=self.backend, sequence_id=str(site.get("sequence_id", "")),
            position=int(site.get("position", -1)), stage=str(site.get("stage", "")),
            layer=layer, site=str(site.get("site", "")), specialist="recurrent-dynamics",
            predecessor_generation=int(site.get("predecessor_generation", -1)),
            predecessor_sha256=str(site.get("predecessor_snapshot_sha256", "")),
            intervention_order=int(site.get("intervention_order", -1)),
            dependencies=dependencies, request_sha256=str(request.get("request_sha256", "")),
            verb=str(site.get("verb", "observe")),
        )
        qkv_name = self._weight("attn_qkv", layer, required=False)
        gate_name = self._weight("attn_gate", layer, required=False)
        beta_name = self._weight("ssm_beta", layer, required=False)
        alpha_name = self._weight("ssm_alpha", layer, required=False)
        out_name = self._weight("ssm_out", layer, required=False)
        if out_name is None:
            out_name = self._weight("attn_out", layer, required=False)
        if any(name is None for name in (qkv_name, gate_name, beta_name, alpha_name, out_name)):
            raise ResidentQwenError("recurrent transition tensors are unavailable")
        def output_width(name: str) -> int:
            shape = tuple(int(dim) for dim in self._tensor_shapes[name]["shape"])
            if len(shape) != 2:
                raise ResidentQwenError("recurrent transition tensor shape is invalid")
            if shape[1] == normalized.size:
                return shape[0]
            if shape[0] == normalized.size:
                return shape[1]
            raise ResidentQwenError("recurrent transition tensor input width is invalid")
        nk = int(self._meta(f"{self.architecture}.ssm.group_count", self._meta("ssm.group_count", 1)))
        key_dim = int(self._meta(f"{self.architecture}.ssm.state_size", self._meta("ssm.state_size", 1)))
        inner = int(self._meta(f"{self.architecture}.ssm.inner_size", self._meta("ssm.inner_size", 0)))
        nv = int(self._meta(f"{self.architecture}.ssm.time_step_rank", self._meta("ssm.time_step_rank", 0))) or nk
        value_dim = max(1, inner // nv) if inner else key_dim
        qkv_width = output_width(qkv_name)
        gate_width = output_width(gate_name)
        if (qkv_width != 2 * nk * key_dim + nv * value_dim
                or gate_width != nv * value_dim
                or output_width(beta_name) != nv or output_width(alpha_name) != nv):
            raise ResidentQwenError("recurrent transition projection dimensions are invalid")
        out_shape = tuple(int(dim) for dim in self._tensor_shapes[out_name]["shape"])
        if len(out_shape) != 2 or (normalized.size, nv * value_dim) not in (
                out_shape, out_shape[::-1]):
            raise ResidentQwenError("recurrent transition output dimensions are invalid")
        history_rows = self._conv_history_rows(layer, qkv_width)
        if history_rows == 0:
            # Native recurrent sites exist only for layers with convolution state.
            return None, None, None, None, None, None
        prior_history = _conv_window(arrays.get(f"conv_history.{layer}"), history_rows, qkv_width)
        prior_state = arrays.get(f"recurrent_state.{layer}")
        prior_state = (
            np.zeros((nv, value_dim, key_dim), dtype=np.float32)
            if prior_state is None else np.asarray(prior_state, dtype=np.float32).reshape(nv, value_dim, key_dim)
        )
        recurrent_features = np.concatenate((
            np.asarray(normalized, dtype=np.float32).reshape(-1),
            prior_history.reshape(-1), prior_state.reshape(-1),
        )).astype(np.float32, copy=False)
        successor_shapes = {
            "hidden": {"shape": [int(normalized.size)], "dtype": "<f4", "order": "C"},
            f"conv_history.{layer}": {"shape": [history_rows, qkv_width], "dtype": "<f4", "order": "C"},
            f"recurrent_state.{layer}": {"shape": [nv, value_dim, key_dim], "dtype": "<f4", "order": "C"},
        }
        potential_cost = {
            "native_ops_omitted": 5,
            "flops": int(2 * normalized.size * (
                qkv_width + gate_width + 2 * nv + nv * value_dim
            )),
        }
        site_arrays = dict(arrays)
        site_arrays["recurrent_features"] = recurrent_features
        if site.get("verb") not in {"replace", "propose"}:
            return binding, None, native_state, successor_shapes, recurrent_features, potential_cost
        metadata = {
            "backend": self.backend, "native_state_applicability": native_state,
            "successor_shapes": successor_shapes,
        }
        provider = self._graph_site_candidate_provider
        if callable(provider):
            selected = provider(request, site_arrays, metadata)
        else:
            policies = request.get("policies")
            graph_state = policies.get("graph_sites") if isinstance(policies, Mapping) else None
            if not isinstance(graph_state, Mapping):
                return binding, None, native_state, successor_shapes, recurrent_features, potential_cost
            selected = candidates_for_site(
                {"source_sha256": self.source_sha256, "graph_sites": graph_state},
                request, site_arrays, metadata,
            )
        if selected is None:
            selections = []
        elif isinstance(selected, Mapping):
            selections = [selected]
        elif isinstance(selected, list) and len(selected) <= 16:
            selections = selected
        else:
            raise ResidentQwenError("recurrent candidate provider returned an invalid selection")
        if any(not isinstance(item, Mapping) or item.get("invocation") != binding
               for item in selections):
            raise ResidentQwenError("selected recurrent method has a stale graph-site binding")
        return binding, selections or None, native_state, successor_shapes, recurrent_features, potential_cost
    @staticmethod
    def _recurrent_graph_receipt(capture: Mapping[str, Any]) -> dict[str, Any] | None:
        from .graph_site import (
            ABSTENTION_SCHEMA, MAX_TRAINING_INPUT_VALUES, MAX_TRAINING_OUTPUT_VALUES,
        )
        binding = capture.get("binding")
        if not isinstance(binding, Mapping):
            return None
        input_vector = capture.get("recurrent_features")
        target = capture.get("successor_vector")
        state = capture.get("successor_state")
        shapes = capture.get("successor_shapes")
        cost = capture.get("potential_cost")
        width = int(target.size) if isinstance(target, np.ndarray) else 0
        if (capture.get("refusal") is not None or not isinstance(input_vector, np.ndarray)
                or not isinstance(target, np.ndarray) or not isinstance(state, Mapping)
                or not isinstance(shapes, Mapping) or not isinstance(cost, Mapping)):
            reason = "unsupported-state"
        elif input_vector.size > MAX_TRAINING_INPUT_VALUES:
            reason = "input-capacity"
        elif target.size > MAX_TRAINING_OUTPUT_VALUES:
            reason = "output-capacity"
        elif binding.get("verb") == "replace" and capture.get("replaced") is True:
            observation = {
                "schema": "cassifi.graph-site-observation.v1", "invocation": binding,
                "method_key": capture.get("method_key"),
                "method_generation": capture.get("method_generation"),
                "observed_error": None, "task_outcome": "unknown",
                "native_ops_omitted": cost["native_ops_omitted"],
                "omitted_ops": ["attn_qkv", "attn_gate", "ssm_beta", "ssm_alpha", "ssm_out"],
                "successor_state": state, "cost": dict(cost),
            }
            return {"graph_site_observation": observation}
        elif binding.get("verb") == "propose" and isinstance(capture.get("proposal"), Mapping):
            proposal = capture["proposal"]
            native_output_sha256 = _graph_f32_payload(target)["sha256"]
            added_flops = proposal["added_flops"]
            observation = {
                "schema": "cassifi.graph-site-observation.v1", "invocation": binding,
                "method_key": proposal["method_key"],
                "method_generation": proposal["method_generation"],
                "observed_error": None, "task_outcome": "unknown",
                "native_ops_omitted": 0, "omitted_ops": [],
                "successor_state": state,
                "cost": {"native_ops_omitted": 0, "flops": added_flops},
                "intervention": {
                    "mode": "propose",
                    "native_output_sha256": native_output_sha256,
                    "candidate_output_sha256": proposal["candidate_output_sha256"],
                    "accepted": proposal["candidate_output_sha256"] == native_output_sha256,
                    "native_ops_executed": cost["native_ops_omitted"],
                    "added_flops": added_flops,
                },
            }
            return {"graph_site_observation": observation}
        elif binding.get("verb") not in {"observe", "replace"}:
            reason = "unsupported-state"
        else:
            reason = None
        if reason is not None:
            return {"graph_site_abstention": {
                "schema": ABSTENTION_SCHEMA, "invocation": binding,
                "reason": reason, "input_values": int(input_vector.size) if isinstance(input_vector, np.ndarray) else 0,
                "output_values": width,
                "maximum_input_values": MAX_TRAINING_INPUT_VALUES,
                "maximum_output_values": MAX_TRAINING_OUTPUT_VALUES,
            }}
        return {"graph_site_training": {
            "schema": "cassifi.graph-site-training.v1", "invocation": binding,
            "input": _graph_f32_payload(input_vector),
            "target": _graph_f32_payload(target),
            "native_state_applicability": capture.get("native_state_applicability"),
            "successor_shapes": shapes, "successor_state": state,
            "task_outcome": "unknown", "native_ops_omitted": 0,
            "cost": dict(cost),
        }}
    @staticmethod
    def _attention_memory_receipt(capture: Mapping[str, Any]) -> dict[str, Any] | None:
        from .graph_site import (
            ABSTENTION_SCHEMA, MAX_TRAINING_INPUT_VALUES, MAX_TRAINING_OUTPUT_VALUES,
        )
        binding = capture.get("binding")
        input_vector = capture.get("attn_input")
        state = capture.get("successor_state")
        shapes = capture.get("successor_shapes")
        native = capture.get("native_projection")
        if (not isinstance(binding, Mapping) or not isinstance(input_vector, np.ndarray)
                or not isinstance(state, Mapping) or not isinstance(shapes, Mapping)):
            return None
        projection_ops = int(capture.get("native_projection_ops", 0))
        if binding.get("verb") == "observe" and isinstance(native, tuple) and len(native) == 3:
            target = np.concatenate(native).astype(np.float32, copy=False)
            if input_vector.size <= MAX_TRAINING_INPUT_VALUES and target.size <= MAX_TRAINING_OUTPUT_VALUES:
                return {"graph_site_training": {
                    "schema": "cassifi.graph-site-training.v1", "invocation": binding,
                    "input": _graph_f32_payload(input_vector), "target": _graph_f32_payload(target),
                    "native_state_applicability": capture.get("native_state_applicability"),
                    "successor_shapes": shapes, "successor_state": state,
                    "cost": {
                        "native_ops_omitted": projection_ops,
                        "flops": int(2 * input_vector.size * target.size),
                    },
                    "task_outcome": "unknown",
                }}
            reason = "input-capacity" if input_vector.size > MAX_TRAINING_INPUT_VALUES else "output-capacity"
            output_values = int(target.size)
        else:
            reason = "unsupported-state"
            output_values = sum(int(np.prod(desc["shape"])) for desc in shapes.values())
        return {"graph_site_abstention": {
            "schema": ABSTENTION_SCHEMA, "invocation": binding, "reason": reason,
            "input_values": int(input_vector.size), "output_values": output_values,
            "maximum_input_values": MAX_TRAINING_INPUT_VALUES,
            "maximum_output_values": MAX_TRAINING_OUTPUT_VALUES,
        }}

    def _graph_site_result(
        self, method: Mapping[str, Any], features: np.ndarray, output_width: int,
        method_id: str, input_name: str, output_name: str,
    ) -> np.ndarray | Any:
        inputs, outputs = method.get("input"), method.get("output")
        if not isinstance(inputs, Mapping) or not isinstance(outputs, Mapping):
            raise ResidentQwenError("graph-site method has no tensor descriptors")
        if (inputs.get("name") != input_name or outputs.get("name") != output_name
                or inputs.get("dtype") != "f32" or outputs.get("dtype") != "f32"
                or inputs.get("shape") != [features.size]
                or outputs.get("shape") != [output_width]):
            raise ResidentQwenError("graph-site method does not match the native site")
        rank = method.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 16:
            raise ResidentQwenError("graph-site method rank is invalid")
        a = _finite_array(method.get("A"), name="graph-site method A")
        b = _finite_array(method.get("B"), name="graph-site method B")
        bias = _finite_array(method.get("bias"), name="graph-site method bias")
        if (a.shape != (features.size, rank) or b.shape != (rank, output_width)
                or bias.shape != (output_width,)):
            raise ResidentQwenError("graph-site method coefficient dimensions are invalid")
        if self._device_epoch is not None:
            epoch = self._device_epoch
            evaluate = getattr(epoch, "low_rank_affine", None)
            if not callable(evaluate):
                raise ResidentQwenError("device backend lacks graph-site arithmetic")
            return evaluate(epoch.upload(features), a, b, bias, method_id=method_id)
        return _finite_array((features @ a) @ b + bias, name="graph-site output")

    def _expert_graph_result(
        self, method: Mapping[str, Any], features: np.ndarray, output_width: int,
        method_id: str,
    ) -> np.ndarray | Any:
        descriptor = method.get("input")
        input_name = descriptor.get("name") if isinstance(descriptor, Mapping) else None
        if not isinstance(input_name, str):
            raise ResidentQwenError("expert graph method has no input tensor")
        return self._graph_site_result(
            method, features, output_width, method_id, input_name, "ffn_delta",
        )

    def _head_graph_site(
        self, request: Mapping[str, Any], arrays: Mapping[str, np.ndarray],
        normalized: np.ndarray,
    ) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None, Mapping[str, Any] | None]:
        site = request.get("graph_site")
        if site is None:
            return None, None, None
        if (not isinstance(site, Mapping) or site.get("specialist") != "execution-choice"
                or request.get("stage") != "qwen-head" or request.get("layer") is not None):
            raise ResidentQwenError("execution-choice graph site is invalid")
        dependencies = site.get("dependencies")
        if not isinstance(dependencies, Mapping):
            return None, None, None
        from .graph_site import candidate_for_site, invocation
        native_state = {
            "membrane_profile": _plain(dependencies.get("membrane_profile")),
            "field_epoch_sha256": dependencies.get("field_epoch_sha256"),
        }
        binding = invocation(
            source_sha256=self.source_sha256, architecture=self.architecture,
            backend=self.backend, sequence_id=str(site.get("sequence_id", "")),
            position=int(site.get("position", -1)), stage=str(site.get("stage", "")),
            layer=None, site=str(site.get("site", "")), specialist="execution-choice",
            predecessor_generation=int(site.get("predecessor_generation", -1)),
            predecessor_sha256=str(site.get("predecessor_snapshot_sha256", "")),
            intervention_order=int(site.get("intervention_order", -1)),
            dependencies=dependencies, request_sha256=str(request.get("request_sha256", "")),
            verb=str(site.get("verb", "observe")),
        )
        site_arrays = dict(arrays)
        site_arrays["head_input"] = normalized
        if self._activation_exchange is not None or self._device_membrane is not None:
            return binding, None, native_state
        if site.get("verb") not in {"replace", "assist", "propose"}:
            return binding, None, native_state
        metadata = {"backend": self.backend, "native_state_applicability": native_state}
        provider = self._graph_site_candidate_provider
        if callable(provider):
            selected = provider(request, site_arrays, metadata)
        else:
            policies = request.get("policies")
            graph_state = policies.get("graph_sites") if isinstance(policies, Mapping) else None
            if not isinstance(graph_state, Mapping):
                return binding, None, native_state
            selected = candidate_for_site(
                {"source_sha256": self.source_sha256, "graph_sites": graph_state},
                request, site_arrays, metadata,
            )
        if selected is not None and selected.get("invocation") != binding:
            raise ResidentQwenError("selected execution-choice method has a stale binding")
        return binding, selected, native_state
    @staticmethod
    def _observe_expert_graph(
        route: dict[str, Any], features: np.ndarray, target: np.ndarray,
    ) -> None:
        binding = route.pop("graph_site_binding", None)
        if binding is None:
            return
        route.pop("graph_site_features", None)
        route.pop("graph_site_native_state", None)
        cost = route.pop("graph_site_potential_cost", None)
        route.pop("graph_site_potential_ops", None)
        from .graph_site import (
            ABSTENTION_SCHEMA, MAX_TRAINING_INPUT_VALUES, MAX_TRAINING_OUTPUT_VALUES,
        )
        if (features.size > MAX_TRAINING_INPUT_VALUES or target.size > MAX_TRAINING_OUTPUT_VALUES
                or not isinstance(cost, Mapping)):
            reason = (
                "input-capacity" if features.size > MAX_TRAINING_INPUT_VALUES
                else "output-capacity" if target.size > MAX_TRAINING_OUTPUT_VALUES
                else "unsupported-state"
            )
            route["graph_site_abstention"] = {
                "schema": ABSTENTION_SCHEMA, "invocation": binding, "reason": reason,
                "input_values": int(features.size), "output_values": int(target.size),
                "maximum_input_values": MAX_TRAINING_INPUT_VALUES,
                "maximum_output_values": MAX_TRAINING_OUTPUT_VALUES,
            }
            return
        if binding["verb"] in {"observe", "propose", "replace"}:
            route["graph_site_training"] = {
                "schema": "cassifi.graph-site-training.v1",
                "invocation": binding, "input": _graph_f32_payload(features),
                "target": _graph_f32_payload(target),
                "native_state_applicability": native_state, "cost": cost,
                "native_ops_omitted": 0, "task_outcome": "unknown",
            }
        else:
            route["graph_site_abstention"] = {
                "schema": ABSTENTION_SCHEMA, "invocation": binding,
                "reason": "unsupported-state", "input_values": int(features.size),
                "output_values": int(target.size),
                "maximum_input_values": MAX_TRAINING_INPUT_VALUES,
                "maximum_output_values": MAX_TRAINING_OUTPUT_VALUES,
            }
    def _ffn(self, request: Mapping[str, Any], arrays: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], Mapping[str, Any], Mapping[str, Any] | None]:
        layer = int(request["layer"])
        x = arrays.get("hidden")
        if x is None:
            raise ResidentQwenError("FFN stage requires hidden in snapshot")
        if self._device_epoch is not None and self.architecture == "qwen35":
            epoch = self._device_epoch
            device_x = arrays.pop("_device_hidden", None)
            if device_x is None:
                device_x = epoch.upload(np.asarray(x, dtype=np.float32).reshape(-1))
            device_residual = arrays.pop("_device_attention_residual", None)
            if device_residual is None and arrays.get("attention_residual") is not None:
                device_residual = epoch.upload(arrays["attention_residual"].reshape(-1))
            arrays["hidden"] = self._dense_ffn_device(device_x, device_residual, layer)
            arrays.pop("attention_residual", None)
            return arrays, self._save_state(arrays, request), None
        attention_residual = arrays.get("attention_residual")
        if attention_residual is not None:
            base = np.asarray(attention_residual, dtype=np.float32).reshape(-1)
            residual = base + x.reshape(-1).astype(np.float32, copy=False)
        else:
            residual = x.reshape(-1).astype(np.float32, copy=True)
        residual = self._exchange("ffn.residual", residual, layer=layer)
        y = self._norm(residual, "ffn_norm", layer)
        y = self._exchange("ffn.normalized", y, layer=layer)
        route: dict[str, Any] | None = None
        result = np.zeros_like(residual)
        if self.architecture == "qwen35moe" and self._weight("ffn_gate_inp", layer, required=False) is not None:
            router = self._mat("ffn_gate_inp", y, layer)
            assert router is not None
            router = self._exchange("ffn.router-logits", router, layer=layer)
            probs = _softmax(router)
            probs = self._exchange(
                "ffn.router-probabilities",
                probs,
                layer=layer,
            )
            if np.any(probs < 0) or not np.isclose(
                np.sum(probs, dtype=np.float32),
                np.float32(1.0),
            ):
                probs = np.maximum(probs, np.float32(0.0))
                total = np.sum(probs, dtype=np.float32)
                if total <= 0:
                    raise ResidentQwenError(
                        "field-modulated router probabilities have no support"
                    )
                probs = probs / total
            top_k = int(self._meta(f"{self.architecture}.expert_used_count", self._meta("expert_used_count", min(2, probs.size))))
            top_k = max(1, min(top_k, probs.size))
            params = request.get("parameters") or {}
            supplied = params.get("expert_ids")
            if supplied is not None:
                if not isinstance(supplied, Sequence) or isinstance(supplied, (str, bytes)) or not supplied:
                    raise ResidentQwenError("parameters.expert_ids must be a nonempty sequence")
                ids = np.asarray([int(i) for i in supplied], dtype=np.int64)
                if np.any(ids < 0) or np.any(ids >= probs.size) or len(set(ids.tolist())) != ids.size:
                    raise ResidentQwenError("parameters.expert_ids contains an invalid or duplicate expert")
            else:
                ids = np.argsort(probs)[-top_k:][::-1]
            weights = probs[ids].astype(np.float32, copy=True)
            weights /= np.sum(weights, dtype=np.float32)
            weights = self._exchange(
                "ffn.expert-weights",
                weights,
                layer=layer,
            )
            if np.any(weights < 0) or not np.isclose(
                np.sum(weights, dtype=np.float32),
                np.float32(1.0),
            ):
                weights = np.maximum(weights, np.float32(0.0))
                total = np.sum(weights, dtype=np.float32)
                if total <= 0:
                    raise ResidentQwenError(
                        "field-modulated expert weights have no support"
                    )
                weights = weights / total
            selected_ids = [int(i) for i in ids]
            expert_stems = (
                "ffn_gate_up_exps",
                "ffn_gate_exps",
                "ffn_up_exps",
                "ffn_down_exps",
            )
            expert_tensor_names = [
                name
                for stem in expert_stems
                if (name := self._weight(stem, layer, required=False)) is not None
            ]
            expert_bytes = sum(
                int(self._tensor_shapes[name].get("byte_length", 0))
                // max(1, int(probs.size))
                for name in expert_tensor_names
            )
            resident_before = set(self._resident_experts.get(layer, set()))
            route = {
                "layer": layer,
                "expert_ids": selected_ids,
                "mandatory_experts": selected_ids,
                "expert_bytes": [expert_bytes] * int(probs.size),
                "resident_experts": sorted(resident_before),
                "context_key": (
                    f"layer:{layer}:route:" + ",".join(str(value) for value in selected_ids)
                ),
                "router_probabilities": probs.tolist(),
                "normalized_weights": weights.tolist(),
            }
            features = y.astype(np.float32, copy=False)
            arrays.pop("ffn_input", None)
            arrays["router_logits"] = router
            arrays["router_probabilities"] = probs
            arrays["router_ids"] = ids.astype(np.float32)
            arrays["router_weights"] = weights.copy()
            if bool(params.get("route_only", False)):
                return arrays, self._save_state(arrays, request), route
            if isinstance(request.get("graph_site"), Mapping):
                graph_cost = self._expert_graph_cost(layer, selected_ids, int(probs.size))
            else:
                graph_cost = None
            binding, selected_method = self._expert_graph_site(request, arrays, y)
            if binding is not None and selected_method is not None:
                try:
                    field_output = self._expert_graph_result(
                        selected_method["method"], y, y.size,
                        selected_method["method_key"],
                    )
                except ResidentQwenError as exc:
                    route["graph_site_refusal"] = str(exc)
                else:
                    if self._device_epoch is not None:
                        epoch = self._device_epoch
                        output = self._exchange_device("ffn.output", field_output, layer=layer)
                        arrays["hidden"] = epoch.download(
                            self._exchange_device(
                                "layer.output",
                                epoch.add(epoch.upload(residual), output), layer=layer,
                            )
                        )
                    else:
                        output = self._exchange("ffn.output", field_output, layer=layer)
                        arrays["hidden"] = self._exchange(
                            "layer.output", residual + output, layer=layer,
                        )
                    arrays.pop("attention_residual", None)
                    assert graph_cost is not None
                    route["graph_site_observation"] = {
                        "schema": "cassifi.graph-site-observation.v1",
                        "invocation": binding,
                        "method_key": selected_method["method_key"],
                        "method_generation": selected_method["method_generation"],
                        "observed_error": None,
                        "task_outcome": "unknown",
                        "native_ops_omitted": graph_cost["native_ops_omitted"],
                        "omitted_ops": graph_cost["omitted_ops"],
                        "cost": {
                            "native_ops_omitted": graph_cost["native_ops_omitted"],
                            "flops": graph_cost["flops"],
                        },
                    }
                    route["native_ops_omitted"] = graph_cost["native_ops_omitted"]
                    return arrays, self._save_state(arrays, request), route
            if binding is not None:
                route["graph_site_binding"] = binding
                assert graph_cost is not None
                route["graph_site_native_state"] = {
                    "membrane_profile": _plain(request["graph_site"]["dependencies"]["membrane_profile"]),
                    "field_epoch_sha256": request["graph_site"]["dependencies"]["field_epoch_sha256"],
                    "expert_route": {"expert_ids": selected_ids, "top_k": len(selected_ids)},
                }
                route["graph_site_features"] = features.copy()
                route["graph_site_potential_cost"] = {
                    "native_ops_omitted": graph_cost["native_ops_omitted"],
                    "flops": graph_cost["flops"],
                }
            prefetch_ids = params.get("prefetch_experts", selected_ids)
            if not isinstance(prefetch_ids, Sequence) or isinstance(prefetch_ids, (str, bytes)):
                raise ResidentQwenError("parameters.prefetch_experts must be a sequence")
            prefetch_started_ns = time.perf_counter_ns()
            prefetch = getattr(self._bank, "prefetch", None)
            residency = getattr(self._bank, "residency", None)
            residency_rows: list[Mapping[str, Any]] = []
            for raw_eid in prefetch_ids:
                eid = int(raw_eid)
                for tensor_name in expert_tensor_names:
                    if prefetch is not None:
                        prefetch(tensor_name, eid)
                    if residency is not None:
                        row = residency(tensor_name, eid)
                        if isinstance(row, Mapping):
                            residency_rows.append(
                                {"tensor": tensor_name, "expert": eid, **dict(row)}
                            )
                self._resident_experts.setdefault(layer, set()).add(eid)
            device_result = None
            load_cost_ns = time.perf_counter_ns() - prefetch_started_ns
            if residency_rows:
                route["residency"] = residency_rows
            for eid, weight in zip(ids, weights):
                if self._device_epoch is not None:
                    epoch = self._device_epoch
                    if device_result is None:
                        device_y = epoch.upload(y)
                    expert_id = int(eid)
                    gate_name = self._weight("ffn_gate_exps", layer, required=False)
                    up_name = self._weight("ffn_up_exps", layer, required=False)
                    if gate_name is not None and up_name is not None:
                        g, u = epoch.matvec_many(
                            (gate_name, up_name), device_y,
                            experts=(expert_id, expert_id),
                        )
                    else:
                        packed_name = self._weight("ffn_gate_up_exps", layer, required=False)
                        if packed_name is None:
                            raise ResidentQwenError("MoE expert gate/up tensors are incomplete")
                        packed = epoch.matvec(packed_name, device_y, expert=expert_id)
                        if packed.count % 2:
                            raise ResidentQwenError("MoE expert packed gate/up width is odd")
                        half = packed.count // 2
                        g, u = epoch.view(packed, 0, half), epoch.view(packed, half, half)
                    g = self._exchange_device("ffn.expert-gate", g, layer=layer, expert=expert_id)
                    u = self._exchange_device("ffn.expert-up", u, layer=layer, expert=expert_id)
                    active = self._exchange_device(
                        "ffn.expert-silu", epoch.mul(epoch.silu(g), u),
                        layer=layer, expert=expert_id,
                    )
                    down_name = self._weight("ffn_down_exps", layer)
                    assert down_name is not None
                    d = self._exchange_device(
                        "ffn.expert-down", epoch.matvec(down_name, active, expert=expert_id),
                        layer=layer, expert=expert_id,
                    )
                    weighted = self._exchange_device(
                        "ffn.expert-weighted", epoch.scale(d, float(weight)),
                        layer=layer, expert=expert_id,
                    )
                    device_result = weighted if device_result is None else epoch.add(device_result, weighted)
                    continue
                g, u = self._mat_many(
                    (("ffn_gate_exps", int(eid)), ("ffn_up_exps", int(eid))),
                    y,
                    layer,
                    required=False,
                )
                if g is None or u is None:
                    gu = self._mat("ffn_gate_up_exps", y, layer, expert=int(eid), required=False)
                    if gu is None or gu.size % 2:
                        raise ResidentQwenError("MoE expert gate/up tensors are incomplete")
                    half = gu.size // 2
                    g, u = gu[:half], gu[half:]
                expert_id = int(eid)
                g = self._exchange(
                    "ffn.expert-gate",
                    g,
                    layer=layer,
                    expert=expert_id,
                )
                u = self._exchange(
                    "ffn.expert-up",
                    u,
                    layer=layer,
                    expert=expert_id,
                )
                activated = self._exchange(
                    "ffn.expert-silu",
                    _silu(g) * u,
                    layer=layer,
                    expert=expert_id,
                )
                d = self._mat(
                    "ffn_down_exps",
                    activated,
                    layer,
                    expert=expert_id,
                )
                if d is None:
                    raise ResidentQwenError("MoE expert down tensor is incomplete")
                d = self._exchange(
                    "ffn.expert-down",
                    d,
                    layer=layer,
                    expert=expert_id,
                )
                weighted = self._exchange(
                    "ffn.expert-weighted",
                    np.float32(weight) * d,
                    layer=layer,
                    expert=expert_id,
                )
                result += weighted
            evict = getattr(self._bank, "evict", None)
            evict_ids = params.get("evict_experts", [])
            if evict is not None and isinstance(evict_ids, Sequence) and not isinstance(evict_ids, (str, bytes)):
                for raw_eid in evict_ids:
                    eid = int(raw_eid)
                    if eid in set(selected_ids):
                        continue
                    for tensor_name in expert_tensor_names:
                        evict(tensor_name, eid)
                    self._resident_experts.setdefault(layer, set()).discard(eid)
            selection = params.get("expert_selection")
            if not isinstance(selection, Mapping):
                selection = {}
            route["expert_observation"] = {
                "layer": layer,
                "context_key": str(
                    selection.get("context_key", route["context_key"])
                ),
                "previous_context_key": selection.get("previous_context_key"),
                "requested_experts": selected_ids,
                "hit_experts": sorted(set(selected_ids) & resident_before),
                "miss_experts": sorted(set(selected_ids) - resident_before),
                "load_cost_ns": int(load_cost_ns),
                "method": str(selection.get("method", "baseline")),
                "prefetch_experts": [int(value) for value in prefetch_ids],
                "evict_experts": [int(value) for value in evict_ids],
            }
            if device_result is not None:
                epoch = self._device_epoch
                shared_names = tuple(
                    self._weight(stem, layer, required=False)
                    for stem in ("ffn_gate_inp_shexp", "ffn_gate_shexp", "ffn_up_shexp")
                )
                if all(name is not None for name in shared_names):
                    selector_proj, shared_gate, shared_up = epoch.matvec_many(
                        shared_names, device_y
                    )
                    selector_proj = self._exchange_device(
                        "ffn.shared-selector", selector_proj, layer=layer
                    )
                    selector = self._exchange_device(
                        "ffn.shared-selector-activation",
                        epoch.sigmoid(selector_proj), layer=layer,
                    )
                    shared_gate = self._exchange_device(
                        "ffn.shared-gate", shared_gate, layer=layer
                    )
                    shared_up = self._exchange_device(
                        "ffn.shared-up", shared_up, layer=layer
                    )
                    active = self._exchange_device(
                        "ffn.shared-silu",
                        epoch.mul(epoch.silu(shared_gate), shared_up), layer=layer,
                    )
                    down_name = self._weight("ffn_down_shexp", layer, required=False)
                    if down_name is None:
                        raise ResidentQwenError("shared MoE down tensor is incomplete")
                    shared_down = self._exchange_device(
                        "ffn.shared-down", epoch.matvec(down_name, active), layer=layer
                    )
                    shared_weighted = self._exchange_device(
                        "ffn.shared-weighted",
                        epoch.mul(shared_down, selector),
                        layer=layer,
                    )
                    device_result = epoch.add(device_result, shared_weighted)
                if "graph_site_binding" in route:
                    self._observe_expert_graph(route, route["graph_site_features"], epoch.download(device_result))
                output = self._exchange_device("ffn.output", device_result, layer=layer)
                arrays["hidden"] = epoch.download(
                    self._exchange_device(
                        "layer.output",
                        epoch.add(epoch.upload(residual), output), layer=layer,
                    )
                )
                arrays.pop("attention_residual", None)
                return arrays, self._save_state(arrays, request), route
            shared_gate_proj, shared_gate, shared_up = self._mat_many(
                (
                    ("ffn_gate_inp_shexp", None),
                    ("ffn_gate_shexp", None),
                    ("ffn_up_shexp", None),
                ),
                y,
                layer,
                required=False,
            )
            if shared_gate_proj is not None and shared_gate is not None and shared_up is not None:
                shared_gate_proj = self._exchange(
                    "ffn.shared-selector",
                    shared_gate_proj,
                    layer=layer,
                )
                shared_selector = self._exchange(
                    "ffn.shared-selector-activation",
                    np.asarray(
                        _sigmoid(shared_gate_proj),
                        dtype=np.float32,
                    ),
                    layer=layer,
                )
                shared_gate = self._exchange(
                    "ffn.shared-gate",
                    shared_gate,
                    layer=layer,
                )
                shared_up = self._exchange(
                    "ffn.shared-up",
                    shared_up,
                    layer=layer,
                )
                shared_active = self._exchange(
                    "ffn.shared-silu",
                    _silu(shared_gate) * shared_up,
                    layer=layer,
                )
                shared_down = self._mat("ffn_down_shexp", shared_active, layer, required=False)
                if shared_down is None:
                    raise ResidentQwenError("shared MoE down tensor is incomplete")
                shared_down = self._exchange(
                    "ffn.shared-down",
                    shared_down,
                    layer=layer,
                )
                shared_weighted = self._exchange(
                    "ffn.shared-weighted",
                    np.float32(shared_selector.reshape(-1)[0])
                    * shared_down,
                    layer=layer,
                )
                result += shared_weighted
        else:
            gate, up = self._mat_many(
                (("ffn_gate", None), ("ffn_up", None)),
                y,
                layer,
            )
            if gate is None or up is None:
                raise ResidentQwenError("dense FFN tensors are incomplete")
            gate = self._exchange("ffn.dense-gate", gate, layer=layer)
            up = self._exchange("ffn.dense-up", up, layer=layer)
            activated = self._exchange(
                "ffn.dense-silu",
                _silu(gate) * up,
                layer=layer,
            )
            down = self._mat("ffn_down", activated, layer)
            if down is None:
                raise ResidentQwenError("dense FFN tensors are incomplete")
            result = self._exchange("ffn.dense-down", down, layer=layer)
        if route is not None and "graph_site_binding" in route:
            self._observe_expert_graph(route, route["graph_site_features"], result)
        result = self._exchange("ffn.output", result, layer=layer)
        arrays["hidden"] = self._exchange(
            "layer.output",
            residual + result,
            layer=layer,
        )
        arrays.pop("attention_residual", None)
        return arrays, self._save_state(arrays, request), route

    def _head(
        self, request: Mapping[str, Any], arrays: dict[str, np.ndarray],
    ) -> tuple[dict[str, np.ndarray], Mapping[str, Any], int | None, bool, Mapping[str, Any] | None]:
        x = arrays.get("hidden")
        if x is None:
            raise ResidentQwenError("head stage requires hidden in snapshot")
        graph_receipt: Mapping[str, Any] | None = None
        head_candidate_logits: np.ndarray | None = None
        head_intervention: dict[str, Any] | None = None
        parameters = request.get("parameters")
        should_sample = not isinstance(parameters, Mapping) or bool(
            parameters.get("sample", True)
        )
        if not should_sample:
            snapshot = request.get("snapshot")
            if (
                "logits" not in arrays
                and isinstance(snapshot, Mapping)
                and snapshot
            ):
                return arrays, _plain(dict(snapshot)), None, False, None
            arrays.pop("logits", None)
            return arrays, self._save_state(arrays, request), None, False, None
        sampler = request.get("sampler") or {}
        mode = str(sampler.get("mode", "greedy"))
        if self._device_epoch is not None:
            epoch = self._device_epoch
            device_x = self._exchange_device("head.input", epoch.upload(x.reshape(-1)))
            norm_name = self._weight("output_norm", None)
            output_name = self._weight("output", None)
            assert norm_name is not None and output_name is not None
            normalized = self._exchange_device(
                "head.normalized",
                epoch.norm_rows(
                    device_x, row_width=device_x.count, epsilon=1e-6,
                    sum_squares=False, weight_name=norm_name,
                ),
            )
            normalized_host = epoch.download(normalized)
            output_shape = tuple(int(v) for v in self._tensor_shapes[output_name]["shape"])
            if len(output_shape) != 2:
                raise ResidentQwenError("output projection shape is invalid")
            if output_shape[1] == normalized_host.size:
                head_width = output_shape[0]
            elif output_shape[0] == normalized_host.size:
                head_width = output_shape[1]
            else:
                raise ResidentQwenError("output projection input width is invalid")
            binding, selected, native_state = self._head_graph_site(
                request, arrays, normalized_host,
            )
            if selected is not None:
                try:
                    candidate_device = self._graph_site_result(
                        selected["method"], normalized_host, head_width,
                        selected["method_key"], "head_input", "logits",
                    )
                    candidate_logits = epoch.download(candidate_device)
                    verb = binding["verb"]
                    if verb == "replace":
                        device_logits = candidate_device
                        graph_receipt = {"graph_site_observation": {
                            "schema": "cassifi.graph-site-observation.v1",
                            "invocation": binding, "method_key": selected["method_key"],
                            "method_generation": selected["method_generation"],
                            "observed_error": None, "task_outcome": "unknown",
                            "native_ops_omitted": 1,
                        }}
                    else:
                        native_device = self._exchange_device(
                            "head.logits", epoch.matvec(output_name, normalized),
                        )
                        native_logits = epoch.download(native_device)
                        head_candidate_logits = candidate_logits
                        head_intervention = {
                            "binding": binding, "selected": selected,
                            "input": normalized_host.copy(), "native_logits": native_logits.copy(),
                        }
                        if verb == "assist":
                            raw_scale = request["graph_site"].get("correction_scale", 0.25)
                            if (isinstance(raw_scale, bool) or not isinstance(raw_scale, (int, float))
                                    or not math.isfinite(raw_scale) or not 0.0 < raw_scale <= 1.0):
                                raise ResidentQwenError("graph-site correction_scale must be between zero and one")
                            scale = float(raw_scale)
                            corrected = native_logits + np.float32(scale) * (candidate_logits - native_logits)
                            device_logits = self._exchange_device("head.logits", epoch.upload(corrected))
                            head_intervention["correction_scale"] = scale
                        else:
                            device_logits = native_device
                except (KeyError, ResidentQwenError):
                    selected = None
                    from .graph_site import ABSTENTION_SCHEMA, MAX_TRAINING_INPUT_VALUES, MAX_TRAINING_OUTPUT_VALUES
                    graph_receipt = {"graph_site_abstention": {
                        "schema": ABSTENTION_SCHEMA, "invocation": binding,
                        "reason": "unsupported-state", "input_values": int(normalized_host.size),
                        "output_values": int(head_width),
                        "maximum_input_values": MAX_TRAINING_INPUT_VALUES,
                        "maximum_output_values": MAX_TRAINING_OUTPUT_VALUES,
                    }}
                    device_logits = self._exchange_device(
                        "head.logits", epoch.matvec(output_name, normalized),
                    )
            else:
                device_logits = self._exchange_device(
                    "head.logits", epoch.matvec(output_name, normalized),
                )
            if mode in {"categorical", "temperature"}:
                temp = float(sampler.get("temperature", 1.0))
                if not math.isfinite(temp) or temp <= 0:
                    raise ResidentQwenError("sampler temperature must be positive")
                device_probs = self._exchange_device(
                    "head.probabilities",
                    epoch.softmax(epoch.scale(device_logits, 1.0 / temp)),
                )
                logits, probs = epoch.download_many([device_logits, device_probs])
            else:
                logits = epoch.download(device_logits)
                probs = None
            if binding is not None and binding["verb"] == "observe":
                from .graph_site import ABSTENTION_SCHEMA, MAX_TRAINING_INPUT_VALUES, MAX_TRAINING_OUTPUT_VALUES
                if normalized_host.size > MAX_TRAINING_INPUT_VALUES or logits.size > MAX_TRAINING_OUTPUT_VALUES:
                    reason = "input-capacity" if normalized_host.size > MAX_TRAINING_INPUT_VALUES else "output-capacity"
                    graph_receipt = {"graph_site_abstention": {
                        "schema": ABSTENTION_SCHEMA, "invocation": binding, "reason": reason,
                        "input_values": int(normalized_host.size), "output_values": int(logits.size),
                    }}
                else:
                    graph_receipt = {"graph_site_training": {
                        "schema": "cassifi.graph-site-training.v1", "invocation": binding,
                        "input": _graph_f32_payload(normalized_host),
                        "target": _graph_f32_payload(logits),
                        "native_state_applicability": native_state,
                        "cost": {"native_ops_omitted": 1, "flops": int(4 * int(normalized_host.size) * int(head_width))},
                    }}
            elif binding is not None and binding["verb"] == "replace" and selected is None:
                graph_receipt = {"graph_site_abstention": {
                    "schema": "cassifi.graph-site-abstention.v1",
                    "invocation": binding, "reason": "unsupported-state",
                    "input_values": int(normalized_host.size), "output_values": int(logits.size),
                }}
        else:
            x = self._exchange("head.input", x.reshape(-1))
            y = self._norm(x, "output_norm", None)
            y = self._exchange("head.normalized", y)
            output_name = self._weight("output", None)
            if output_name is None:
                raise ResidentQwenError("output projection is absent")
            output_shape = tuple(int(v) for v in self._tensor_shapes[output_name]["shape"])
            if len(output_shape) != 2:
                raise ResidentQwenError("output projection shape is invalid")
            if output_shape[1] == y.size:
                head_width = output_shape[0]
            elif output_shape[0] == y.size:
                head_width = output_shape[1]
            else:
                raise ResidentQwenError("output projection input width is invalid")
            binding, selected, native_state = self._head_graph_site(request, arrays, y)
            if selected is not None:
                try:
                    candidate_logits = self._graph_site_result(
                        selected["method"], y, head_width, selected["method_key"],
                        "head_input", "logits",
                    )
                except (KeyError, ResidentQwenError):
                    selected = None
                    graph_receipt = {"graph_site_abstention": {
                        "schema": "cassifi.graph-site-abstention.v1",
                        "invocation": binding, "reason": "unsupported-state",
                        "input_values": int(y.size), "output_values": int(head_width),
                    }}
                    logits = self._mat("output", y, None)
                    if logits is not None:
                        logits = self._exchange("head.logits", logits)
                else:
                    candidate_logits = np.asarray(candidate_logits, dtype=np.float32)
                    if binding["verb"] == "replace":
                        logits = candidate_logits
                        graph_receipt = {"graph_site_observation": {
                            "schema": "cassifi.graph-site-observation.v1",
                            "invocation": binding, "method_key": selected["method_key"],
                            "method_generation": selected["method_generation"],
                            "observed_error": None, "task_outcome": "unknown",
                            "native_ops_omitted": 1,
                        }}
                    else:
                        native_logits = self._mat("output", y, None)
                        if native_logits is None:
                            raise ResidentQwenError("output projection is absent")
                        native_logits = self._exchange("head.logits", native_logits)
                        head_candidate_logits = candidate_logits
                        head_intervention = {
                            "binding": binding, "selected": selected, "input": y.copy(),
                            "native_logits": native_logits.copy(),
                        }
                        if binding["verb"] == "assist":
                            raw_scale = request["graph_site"].get("correction_scale", 0.25)
                            if (isinstance(raw_scale, bool) or not isinstance(raw_scale, (int, float))
                                    or not math.isfinite(raw_scale) or not 0.0 < raw_scale <= 1.0):
                                raise ResidentQwenError("graph-site correction_scale must be between zero and one")
                            scale = float(raw_scale)
                            logits = native_logits + np.float32(scale) * (candidate_logits - native_logits)
                            head_intervention["correction_scale"] = scale
                        else:
                            logits = native_logits
            else:
                logits = self._mat("output", y, None)
                if logits is not None:
                    logits = self._exchange("head.logits", logits)
            if logits is None:
                raise ResidentQwenError("output projection is absent")
            if binding is not None and binding["verb"] == "observe":
                from .graph_site import ABSTENTION_SCHEMA, MAX_TRAINING_INPUT_VALUES, MAX_TRAINING_OUTPUT_VALUES
                if y.size > MAX_TRAINING_INPUT_VALUES or logits.size > MAX_TRAINING_OUTPUT_VALUES:
                    reason = "input-capacity" if y.size > MAX_TRAINING_INPUT_VALUES else "output-capacity"
                    graph_receipt = {"graph_site_abstention": {
                        "schema": ABSTENTION_SCHEMA, "invocation": binding, "reason": reason,
                        "input_values": int(y.size), "output_values": int(logits.size),
                    }}
                else:
                    graph_receipt = {"graph_site_training": {
                        "schema": "cassifi.graph-site-training.v1", "invocation": binding,
                        "input": _graph_f32_payload(y), "target": _graph_f32_payload(logits),
                        "native_state_applicability": native_state,
                        "cost": {"native_ops_omitted": 1, "flops": int(4 * int(y.size) * int(head_width))},
                    }}
            elif binding is not None and binding["verb"] == "replace" and selected is None:
                graph_receipt = {"graph_site_abstention": {
                    "schema": "cassifi.graph-site-abstention.v1",
                    "invocation": binding, "reason": "unsupported-state",
                    "input_values": int(y.size), "output_values": int(logits.size),
                }}
            probs = None
        arrays["logits"] = logits
        if mode == "greedy":
            token = int(np.argmax(logits))
        elif mode in {"categorical", "temperature"}:
            temp = float(sampler.get("temperature", 1.0))
            if not math.isfinite(temp) or temp <= 0:
                raise ResidentQwenError("sampler temperature must be positive")
            if probs is None:
                probs = self._exchange(
                    "head.probabilities",
                    _softmax(logits / np.float32(temp)),
                )
            if np.any(probs < 0) or not np.isclose(
                np.sum(probs, dtype=np.float32),
                np.float32(1.0),
            ):
                probs = np.maximum(probs, np.float32(0.0))
                total = np.sum(probs, dtype=np.float32)
                if total <= 0:
                    raise ResidentQwenError(
                        "field-modulated sampling probabilities have no support"
                    )
                probs = probs / total
            top_k = int(sampler.get("top_k", 0))
            if top_k > 0 and top_k < probs.size:
                ids = np.argsort(probs)[-top_k:]
                p = probs[ids]
                p /= np.sum(p, dtype=np.float32)
            else:
                ids, p = np.arange(probs.size), probs
            draw = float(sampler.get("draw", 0.0))
            if not math.isfinite(draw) or draw < 0 or draw >= 1:
                raise ResidentQwenError(
                    "categorical sampler requires draw in [0,1)"
                )
            token = int(
                ids[
                    min(
                        len(ids) - 1,
                        int(np.searchsorted(np.cumsum(p), draw, side="right")),
                    )
                ]
            )
        else:
            raise ResidentQwenError(f"unsupported sampler mode {mode!r}")
        if head_intervention is not None:
            selected = head_intervention["selected"]
            candidate_logits = np.asarray(head_candidate_logits, dtype=np.float32)
            native_logits = head_intervention["native_logits"]
            verb = head_intervention["binding"]["verb"]
            rank = int(selected["method"]["rank"])
            intervention = {
                "mode": verb,
                "native_output_sha256": _graph_state_descriptor(native_logits)["sha256"],
                "candidate_output_sha256": _graph_state_descriptor(candidate_logits)["sha256"],
                "native_ops_executed": 1,
                "added_flops": int(2 * (head_intervention["input"].size * rank
                                         + rank * candidate_logits.size)),
            }
            if verb == "assist":
                intervention["correction_scale"] = head_intervention["correction_scale"]
                intervention["committed_output_sha256"] = _graph_state_descriptor(logits)["sha256"]
            else:
                intervention["accepted"] = _sample_logits(candidate_logits, sampler) == token
            graph_receipt = {"graph_site_observation": {
                "schema": "cassifi.graph-site-observation.v1",
                "invocation": head_intervention["binding"],
                "method_key": selected["method_key"],
                "method_generation": selected["method_generation"],
                "observed_error": None, "task_outcome": "unknown",
                "native_ops_omitted": 0, "intervention": intervention,
            }}
            if verb == "propose":
                graph_receipt["graph_site_observation"]["candidate_token"] = _sample_logits(
                    candidate_logits, sampler,
                )
                graph_receipt["graph_site_observation"]["native_token"] = token
        eos = self._meta("tokenizer.ggml.eos_token_id", None)
        return (
            arrays,
            self._save_state(arrays, request),
            token,
            eos is not None and token == int(eos),
            graph_receipt,
        )

    def execute_visual_stage(
        self,
        request: Mapping[str, Any],
        *,
        image_png: bytes,
        activation_exchange: Callable[[str, np.ndarray], np.ndarray],
    ) -> Mapping[str, Any]:
        """Encode one transient image inside the owner's active membrane epoch."""

        if self._closed:
            raise ResidentQwenError("executor is closed")
        if not isinstance(request, Mapping) or not isinstance(image_png, bytes):
            raise ResidentQwenError(
                "visual stage requires a request and immutable PNG bytes"
            )
        if not callable(activation_exchange):
            raise ResidentQwenError(
                "visual stage requires an owner membrane exchange"
            )
        req = _plain(dict(request))
        if req.get("schema") != VISUAL_STAGE_REQUEST_SCHEMA:
            raise ResidentQwenError("visual stage request schema is invalid")
        if (
            req.get("stage") != "qwen-vision"
            or req.get("source_sha256") != self.source_sha256
        ):
            raise ResidentQwenError(
                "visual stage request does not match the resident model"
            )
        supplied_digest = req.get("request_sha256")
        unsigned = dict(req)
        unsigned.pop("request_sha256", None)
        request_digest = hashlib.sha256(
            canonical_json_bytes(unsigned)
        ).hexdigest()
        if supplied_digest != request_digest:
            raise ResidentQwenError(
                "visual stage request digest does not match its content"
            )
        parameters = req.get("parameters")
        if not isinstance(parameters, Mapping):
            raise ResidentQwenError("visual stage parameters are invalid")
        png_sha256 = hashlib.sha256(image_png).hexdigest()
        if parameters.get("sanitized_png_sha256") != png_sha256:
            raise ResidentQwenError(
                "transient visual payload digest does not match the request"
            )
        encoder = self.ensure_visual_encoder()
        projector_sha256 = str(getattr(encoder, "projector_sha256", ""))
        if parameters.get("projector_sha256") != projector_sha256:
            raise ResidentQwenError(
                "visual request projector identity does not match"
            )
        if (
            len(projector_sha256) != 64
            or any(character not in "0123456789abcdef" for character in projector_sha256)
        ):
            raise ResidentQwenError(
                "Qwen vision encoder has no exact projector identity"
            )
        model_metadata = getattr(encoder, "model_metadata", {})
        compute_backend = (
            str(model_metadata.get("compute_backend", ""))
            if isinstance(model_metadata, Mapping)
            else ""
        )
        if (
            not compute_backend
            or parameters.get("compute_backend") != compute_backend
        ):
            raise ResidentQwenError(
                "visual request compute backend does not match the encoder"
            )
        seen_sites: list[str] = []

        def exchange(site: str, activation: np.ndarray) -> np.ndarray:
            if (
                not isinstance(site, str)
                or not site.startswith("vision.")
                or not self._is_neural_site_kind(site)
            ):
                raise ResidentQwenError(
                    f"undeclared visual neural site {site!r}"
                )
            value = _finite_array(activation, name=f"activation {site}")
            exchanged = _finite_array(
                activation_exchange(site, value),
                name=f"field response {site}",
            )
            if exchanged.shape != value.shape:
                raise ResidentQwenError(
                    f"field response shape disagrees at neural site {site!r}"
                )
            seen_sites.append(site)
            return exchanged

        embeddings = _finite_array(
            encoder.encode_png(image_png, exchange=exchange),
            name="Qwen vision image embeddings",
        )
        if (
            embeddings.ndim != 2
            or embeddings.shape[0] < 1
            or embeddings.shape[1] != 2048
            or embeddings.size > 1_048_576
        ):
            raise ResidentQwenError(
                "Qwen vision encoder returned an invalid image-token matrix"
            )
        block_ids = sorted(
            int(site.removeprefix("vision.block."))
            for site in seen_sites
            if site.startswith("vision.block.")
        )
        if (
            "vision.patch" not in seen_sites
            or "vision.merge" not in seen_sites
            or block_ids != list(range(27))
        ):
            raise ResidentQwenError(
                "Qwen vision encoder did not traverse all 27 declared field sites"
            )
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
        embedding_sha256 = hashlib.sha256(
            embeddings.astype("<f4", copy=False).tobytes(order="C")
        ).hexdigest()
        return {
            "schema": VISUAL_STAGE_RESULT_SCHEMA,
            "operation_id": req["operation_id"],
            "source_sha256": self.source_sha256,
            "stage": "qwen-vision",
            "request_sha256": request_digest,
            "projector_sha256": projector_sha256,
            "sanitized_png_sha256": png_sha256,
            "embedding_shape": list(embeddings.shape),
            "embedding_sha256": embedding_sha256,
            "visual_sites": list(seen_sites),
            "transient_embeddings": embeddings,
            "backend": compute_backend,
        }

    def begin_stage_transaction(self) -> str:
        """Create a private, independently committable sequence of stage snapshots."""
        if self._closed:
            raise ResidentQwenError("executor is closed")
        ticket = uuid.uuid4().hex
        with self._stage_transaction_guard:
            self._stage_transactions[ticket] = {
                "lock": threading.Lock(),
                "working_snapshot": None,
                "working_arrays": None,
                "working_metadata": None,
                "resident_experts": {},
            }
        return ticket

    def _finish_stage_transaction(self, ticket: str, *, commit: bool) -> None:
        if not isinstance(ticket, str) or not ticket:
            raise ResidentQwenError("stage transaction ticket must be a nonempty string")
        with self._stage_transaction_guard:
            transaction = self._stage_transactions.get(ticket)
        if transaction is None:
            return
        lock = transaction["lock"]
        lock.acquire()
        try:
            with self._stage_transaction_guard:
                if self._stage_transactions.get(ticket) is not transaction:
                    return
                if commit:
                    if transaction["working_snapshot"] is not None:
                        self._working_snapshot = transaction["working_snapshot"]
                        self._working_arrays = transaction["working_arrays"]
                        self._working_metadata = transaction["working_metadata"]
                    for layer, experts in transaction["resident_experts"].items():
                        self._resident_experts.setdefault(layer, set()).update(experts)
                del self._stage_transactions[ticket]
        finally:
            lock.release()

    def seal_stage_transaction(self, ticket: str) -> Mapping[str, Any] | None:
        """Flush the snapshot an owner publication is about to reference.

        Transaction stages publish verified snapshot bytes without flushing
        them. Only the latest stage snapshot continues the model, so one seal
        per owner publication makes exactly that snapshot durable; superseded
        intermediate stage snapshots never pay for a flush. Volatile visual
        snapshots stay process-local by design. Returns the sealed descriptor,
        or ``None`` when nothing durable is pending.
        """
        if not isinstance(ticket, str) or not ticket:
            raise ResidentQwenError("stage transaction ticket must be a nonempty string")
        with self._stage_transaction_guard:
            transaction = self._stage_transactions.get(ticket)
        if transaction is None:
            raise ResidentQwenError("stage transaction ticket is unknown or closed")
        with transaction["lock"]:
            descriptor = transaction["working_snapshot"]
        if descriptor is None or descriptor.get("visual_embedding_id") is not None:
            return None
        return self._snapshots.make_durable(descriptor)

    def commit_stage_transaction(self, ticket: str) -> None:
        """Promote an already-sealed private snapshot cache after owner publish.

        Snapshot bytes and descriptors are immutable and are sealed before
        the owner publishes; commit only changes the executor's local
        working-cache pointer and cannot invalidate the published descriptor.
        Repeated commits are harmless.
        """
        self._finish_stage_transaction(ticket, commit=True)

    def abort_stage_transaction(self, ticket: str) -> None:
        """Discard only private cache state; unsealed blobs stay content-addressed."""
        self._finish_stage_transaction(ticket, commit=False)

    def _run_stage_context(
        self,
        request: Mapping[str, Any],
        *,
        activation_exchange: Callable[[str, np.ndarray], np.ndarray] | None,
        graph_site_candidate_provider: Callable[
            [Mapping[str, Any], Mapping[str, np.ndarray], Mapping[str, Any]],
            Mapping[str, Any] | list[Mapping[str, Any]] | None,
        ] | None,
    ) -> Mapping[str, Any]:
        if activation_exchange is not None and not callable(activation_exchange):
            raise ResidentQwenError("activation_exchange must be callable")
        if graph_site_candidate_provider is not None and not callable(
            graph_site_candidate_provider
        ):
            raise ResidentQwenError("graph_site_candidate_provider must be callable")
        if self._activation_exchange is not None:
            raise ResidentQwenError("resident executor does not permit nested stages")
        self._activation_exchange = activation_exchange
        self._graph_site_candidate_provider = graph_site_candidate_provider
        try:
            bank = getattr(self._bank, "_base_bank", self._bank)
            if (
                activation_exchange is not None
                and WeightBank is not None
                and isinstance(bank, WeightBank)
                and self.backend == "vulkan"
            ):
                membrane = getattr(activation_exchange, "__self__", None)
                if membrane is None or not callable(
                    getattr(membrane, "bind_device", None)
                ):
                    raise ResidentQwenError(
                        "Vulkan neural exchange requires an owner membrane epoch"
                    )
                self._device_membrane = membrane
                self._device_epoch = membrane.bind_device(bank)
            return self._execute_stage(request)
        finally:
            self._activation_exchange = None
            self._device_epoch = None
            self._device_membrane = None
            self._graph_site_candidate_provider = None

    def _execute_transaction_stage(
        self,
        request: Mapping[str, Any],
        *,
        activation_exchange: Callable[[str, np.ndarray], np.ndarray] | None,
        graph_site_candidate_provider: Callable[
            [Mapping[str, Any], Mapping[str, np.ndarray], Mapping[str, Any]],
            Mapping[str, Any] | list[Mapping[str, Any]] | None,
        ] | None,
        ticket: str,
        projection_batcher: _ProjectionBatcher | None = None,
        work_trace: Any | None = None,
    ) -> Mapping[str, Any]:
        trace = work_trace if work_trace is not None else _active_work_trace()
        requested_ns = trace.now() if trace is not None else 0
        with self._stage_transaction_guard:
            transaction = self._stage_transactions.get(ticket)
        if transaction is None:
            raise ResidentQwenError("stage transaction ticket is unknown or closed")
        lock = transaction["lock"]
        lock.acquire()
        if trace is not None:
            _trace_record(
                trace,
                "wait",
                "stage-transaction-lock",
                wait_ns=max(0, trace.now() - requested_ns),
                rows=1,
            )
        started_ns = trace.now() if trace is not None else 0
        try:
            with self._stage_transaction_guard:
                if self._stage_transactions.get(ticket) is not transaction:
                    raise ResidentQwenError("stage transaction ticket is unknown or closed")
                context = copy.copy(self)
                context._working_snapshot = transaction["working_snapshot"]
                context._working_arrays = transaction["working_arrays"]
                context._working_metadata = transaction["working_metadata"]
                context._resident_experts = {
                    layer: set(experts)
                    for layer, experts in transaction["resident_experts"].items()
                }
                context._request_tensor_names = {}
                context._activation_exchange = None
                context._device_epoch = None
                context._device_membrane = None
                context._graph_site_candidate_provider = None
                context._defer_snapshot_durability = True
                if projection_batcher is not None:
                    context._bank = _BatchedWeightBank(self._bank, projection_batcher)
                previous_hits = context.working_snapshot_hits
            result = context._run_stage_context(
                request,
                activation_exchange=activation_exchange,
                graph_site_candidate_provider=graph_site_candidate_provider,
            )
            with self._stage_transaction_guard:
                if self._stage_transactions.get(ticket) is not transaction:
                    raise ResidentQwenError("stage transaction was closed during execution")
                transaction["working_snapshot"] = context._working_snapshot
                transaction["working_arrays"] = context._working_arrays
                transaction["working_metadata"] = context._working_metadata
                transaction["resident_experts"] = context._resident_experts
                self.working_snapshot_hits += max(
                    0, context.working_snapshot_hits - previous_hits
                )
            result_value = dict(result)
            result_value["executor_transaction"] = {
                "schema": "cassifi.executor-stage-transaction.v1",
                "ticket": ticket,
            }
            if trace is not None:
                layer = request.get("layer")
                source = request.get("source_sha256")
                _trace_record(
                    trace,
                    "stage",
                    str(request.get("stage", "")),
                    max(0, trace.now() - started_ns),
                    rows=1,
                    layer=layer if isinstance(layer, int) and not isinstance(layer, bool) else None,
                    source_sha256=source if isinstance(source, str) and source else None,
                    meta={"ticket": ticket},
                )
            return result_value
        finally:
            lock.release()

    def execute_stage(
        self,
        request: Mapping[str, Any],
        *,
        activation_exchange: Callable[[str, np.ndarray], np.ndarray] | None = None,
        stage_transaction: str | None = None,
        graph_site_candidate_provider: Callable[
            [Mapping[str, Any], Mapping[str, np.ndarray], Mapping[str, Any]],
            Mapping[str, Any] | list[Mapping[str, Any]] | None,
        ] | None = None,
    ) -> Mapping[str, Any]:
        """Execute a stage, briefly joining concurrent compatible owner calls."""
        if stage_transaction is not None and (
            not isinstance(stage_transaction, str) or not stage_transaction
        ):
            raise ResidentQwenError("stage_transaction must be a nonempty ticket")
        if not isinstance(request, Mapping):
            raise ResidentQwenError("stage request must be a mapping")
        transactional = stage_transaction is not None
        base_key = (
            request.get("stage"), request.get("layer"),
            request.get("source_sha256"), transactional,
        )
        priority, cohort_observer = _STAGE_DISPATCH_CONTEXT.get()
        with self._batch_join_condition:
            key = base_key
            group = self._batch_join_groups.get(key)
            duplicate_ticket = (
                transactional
                and self._batch_join_ticket_counts.get(stage_transaction, 0) > 0
            )
            duplicate_operation = group is not None and any(
                item["request"].get("operation_id") == request.get("operation_id")
                for item in group["rows"]
            )
            if duplicate_ticket or duplicate_operation:
                # A row's transaction and operation identity cannot be reused
                # in one native batch. Keep this call isolated instead.
                key = (*base_key, "isolated", uuid.uuid4().hex)
                group = None
            if group is None or len(group["rows"]) >= _MAX_STAGE_COHORT_WIDTH:
                group = {"rows": [], "ready": threading.Event()}
                self._batch_join_groups[key] = group
                leader = True
            else:
                leader = False
            row = {
                "request": request, "exchange": activation_exchange,
                "provider": graph_site_candidate_provider, "ticket": stage_transaction,
                "priority": priority, "cohort_observer": cohort_observer,
            }
            group["rows"].append(row)
            if transactional:
                self._batch_join_ticket_counts[stage_transaction] = (
                    self._batch_join_ticket_counts.get(stage_transaction, 0) + 1
                )
            if not leader:
                self._batch_join_condition.notify_all()
        join_trace = _active_work_trace()
        join_started_ns = join_trace.now() if join_trace is not None else 0

        def record_join_wait() -> None:
            # A leader's batch execution is stage work, recorded by the stage.
            if join_trace is not None:
                _trace_record(
                    join_trace,
                    "wait",
                    "stage-cohort-join",
                    wait_ns=max(0, join_trace.now() - join_started_ns),
                    rows=1,
                    meta={"leader": leader},
                )

        try:
            if leader:
                deadline = time.monotonic() + self._batch_join_window_seconds
                with self._batch_join_condition:
                    while (
                        len(group["rows"]) < _MAX_STAGE_COHORT_WIDTH
                        and not any(item["priority"] == "foreground" for item in group["rows"])
                    ):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        self._batch_join_condition.wait(remaining)
                    if self._batch_join_groups.get(key) is group:
                        self._batch_join_groups.pop(key, None)
                    rows = list(group["rows"])
                record_join_wait()
                try:
                    group["results"] = self.execute_stage_batch(
                        [item["request"] for item in rows],
                        activation_exchanges=[item["exchange"] for item in rows],
                        tickets=(
                            [item["ticket"] for item in rows]
                            if transactional else None
                        ),
                        graph_site_candidate_providers=[item["provider"] for item in rows],
                        cohort_observers=[item["cohort_observer"] for item in rows],
                        defer_state_commit=transactional,
                    )
                except BaseException as exc:
                    group["error"] = exc
                finally:
                    group["ready"].set()
            else:
                group["ready"].wait()
                record_join_wait()
            if "error" in group:
                raise group["error"]
            index = next(i for i, item in enumerate(group["rows"]) if item is row)
            return group["results"][index]
        finally:
            if transactional:
                with self._batch_join_condition:
                    active = self._batch_join_ticket_counts.get(stage_transaction, 0)
                    if active <= 1:
                        self._batch_join_ticket_counts.pop(stage_transaction, None)
                    else:
                        self._batch_join_ticket_counts[stage_transaction] = active - 1

    def _stage_group_member_resources(self) -> dict[str, int]:
        """Per-row reservation for a stage cohort: one core and its activations."""
        width = int(
            self._meta(
                f"{self.architecture}.embedding_length",
                self._meta("embedding_length", 0),
            )
            or 0
        )
        return {"physical_cores": 1, "peak_bytes": 4 * max(1, width)}

    def _acquire_stage_group_reservation(
        self, request_list: Sequence[Mapping[str, Any]], *, cancel_event: Any | None
    ) -> tuple[Any, str, Any] | None:
        """Reserve a whole cohort's cores and bytes before dispatch when wired."""
        if len(request_list) < 2 or self._physical_admission is None:
            return None
        acquire_group = getattr(self._physical_admission, "acquire_group", None)
        if not callable(acquire_group):
            return None
        group_id = f"stage-cohort:{uuid.uuid4().hex}"
        head_operation = request_list[0].get("operation_id")
        lease = acquire_group(
            group_id,
            len(request_list),
            self._stage_group_member_resources(),
            priority=_STAGE_DISPATCH_CONTEXT.get()[0],
            continuation_id=(
                head_operation
                if isinstance(head_operation, str) and head_operation
                else None
            ),
            cancel_event=cancel_event,
        )
        return (self._physical_admission, group_id, lease)

    @staticmethod
    def _release_stage_group_reservation(
        reservation: tuple[Any, str, Any], status: str
    ) -> None:
        """Retire the cohort reservation exactly once with its outcome."""
        admission, group_id, lease = reservation
        release_group = getattr(admission, "release_group", None)
        if callable(release_group):
            release_group(group_id, status=status)
        else:
            lease.retire(status)

    def execute_stage_batch(
        self,
        requests: Sequence[Mapping[str, Any]],
        *,
        activation_exchanges: Sequence[
            Callable[[str, np.ndarray], np.ndarray] | None
        ] | None = None,
        tickets: Sequence[str] | None = None,
        graph_site_candidate_providers: Sequence[
            Callable[
                [Mapping[str, Any], Mapping[str, np.ndarray], Mapping[str, Any]],
                Mapping[str, Any] | None,
            ]
            | None
        ]
        | None = None,
        cohort_observers: Sequence[_StageCohortObserver | None] | None = None,
        defer_state_commit: bool = True,
        cancel_event: Any | None = None,
    ) -> list[Mapping[str, Any]]:
        """Execute compatible one-token rows concurrently with grouped projections."""
        if isinstance(requests, (str, bytes)):
            raise ResidentQwenError("stage batch requests must be a sequence")
        try:
            request_list = list(requests)
        except TypeError as exc:
            raise ResidentQwenError("stage batch requests must be a sequence") from exc
        if not request_list:
            raise ResidentQwenError("stage batch requires at least one request")
        if any(not isinstance(request, Mapping) for request in request_list):
            raise ResidentQwenError("each stage batch request must be a mapping")
        if not isinstance(defer_state_commit, bool):
            raise ResidentQwenError("defer_state_commit must be a boolean")
        if cancel_event is not None and not callable(
            getattr(cancel_event, "is_set", None)
        ):
            raise ResidentQwenError("cancel_event must expose is_set()")
        compatibility = {
            (request.get("stage"), request.get("layer"), request.get("source_sha256"))
            for request in request_list
        }
        if len(compatibility) != 1:
            raise ResidentQwenError(
                "stage batch requests must share stage, layer, and model source"
            )
        operation_ids = [request.get("operation_id") for request in request_list]
        if len(set(operation_ids)) != len(operation_ids):
            raise ResidentQwenError("stage batch operation IDs must be distinct")

        def aligned_values(values: Sequence[Any] | None, label: str, default: Any) -> list[Any]:
            if values is None:
                return [default] * len(request_list)
            if isinstance(values, (str, bytes)):
                raise ResidentQwenError(f"{label} must align with stage batch requests")
            try:
                result = list(values)
            except TypeError as exc:
                raise ResidentQwenError(
                    f"{label} must align with stage batch requests"
                ) from exc
            if len(result) != len(request_list):
                raise ResidentQwenError(f"{label} count does not match stage batch size")
            return result

        exchanges = aligned_values(activation_exchanges, "activation_exchanges", None)
        providers = aligned_values(
            graph_site_candidate_providers,
            "graph_site_candidate_providers",
            None,
        )
        current_observer = _STAGE_DISPATCH_CONTEXT.get()[1]
        observers = aligned_values(
            cohort_observers,
            "cohort_observers",
            current_observer,
        )
        caller_tickets = tickets is not None
        transaction_tickets = aligned_values(tickets, "tickets", None)
        if not caller_tickets:
            transaction_tickets = [
                self.begin_stage_transaction() for _ in request_list
            ]
        if any(
            not isinstance(ticket, str) or not ticket
            for ticket in transaction_tickets
        ) or len(set(transaction_tickets)) != len(transaction_tickets):
            if not caller_tickets:
                for ticket in transaction_tickets:
                    self.abort_stage_transaction(ticket)
            raise ResidentQwenError("stage batch requires one distinct ticket per row")
        if any(
            exchange is not None and not callable(exchange)
            for exchange in exchanges
        ):
            if not caller_tickets:
                for ticket in transaction_tickets:
                    self.abort_stage_transaction(ticket)
            raise ResidentQwenError("each activation exchange must be callable or null")
        if any(
            provider is not None and not callable(provider)
            for provider in providers
        ):
            if not caller_tickets:
                for ticket in transaction_tickets:
                    self.abort_stage_transaction(ticket)
            raise ResidentQwenError(
                "each graph-site candidate provider must be callable or null"
            )
        if any(observer is not None and not callable(observer) for observer in observers):
            if not caller_tickets:
                for ticket in transaction_tickets:
                    self.abort_stage_transaction(ticket)
            raise ResidentQwenError("each cohort observer must be callable or null")

        try:
            reservation = self._acquire_stage_group_reservation(
                request_list, cancel_event=cancel_event
            )
        except BaseException:
            if not caller_tickets:
                for ticket in transaction_tickets:
                    self.abort_stage_transaction(ticket)
            raise
        try:
            work_trace = _active_work_trace()
            batcher = _ProjectionBatcher(
                self._bank, len(request_list), work_trace=work_trace
            )

            def execute_row(index: int) -> Mapping[str, Any]:
                return self._execute_transaction_stage(
                    request_list[index],
                    activation_exchange=exchanges[index],
                    graph_site_candidate_provider=providers[index],
                    ticket=transaction_tickets[index],
                    projection_batcher=batcher,
                    work_trace=work_trace,
                )

            try:
                with ThreadPoolExecutor(
                    max_workers=len(request_list),
                    thread_name_prefix="resident-qwen-stage",
                ) as pool:
                    futures = [pool.submit(execute_row, index) for index in range(len(request_list))]
                    results = [future.result() for future in futures]
            except BaseException:
                if not caller_tickets:
                    for ticket in transaction_tickets:
                        self.abort_stage_transaction(ticket)
                raise
            if not defer_state_commit:
                # Rows returned without a transaction receipt are published by
                # their caller, so their snapshots are sealed before commit.
                try:
                    for ticket in transaction_tickets:
                        self.seal_stage_transaction(ticket)
                except BaseException:
                    if not caller_tickets:
                        for ticket in transaction_tickets:
                            self.abort_stage_transaction(ticket)
                    raise
                for ticket in transaction_tickets:
                    self.commit_stage_transaction(ticket)
                results = [
                    {key: value for key, value in result.items() if key != "executor_transaction"}
                    for result in results
                ]
            width = len(request_list)
            if work_trace is not None:
                head = request_list[0]
                layer = head.get("layer")
                source = head.get("source_sha256")
                _trace_record(
                    work_trace,
                    "cohort",
                    "stage-batch",
                    rows=width,
                    items=1,
                    layer=layer if isinstance(layer, int) and not isinstance(layer, bool) else None,
                    source_sha256=source if isinstance(source, str) and source else None,
                    meta={"stage": str(head.get("stage", ""))},
                )
            results = [
                {**result, "stage_cohort_width": width}
                for result in results
            ]
            for request, observer in zip(request_list, observers):
                _observe_stage_cohort(observer, width, request)
        except BaseException:
            if reservation is not None:
                self._release_stage_group_reservation(
                    reservation,
                    "cancelled" if _cancel_requested(cancel_event) else "failed",
                )
            raise
        else:
            if reservation is not None:
                self._release_stage_group_reservation(
                    reservation,
                    "cancelled" if _cancel_requested(cancel_event) else "completed",
                )
            return results

    def _execute_stage(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if self._closed: raise ResidentQwenError("executor is closed")
        if not isinstance(request, Mapping) or request.get("schema") not in (None, REQUEST_SCHEMA):
            raise ResidentQwenError("stage request schema is invalid")
        req = _plain(dict(request)); req.setdefault("schema", REQUEST_SCHEMA)
        for key in ("operation_id", "model_program_id", "source_sha256", "stage"):
            if not isinstance(req.get(key), str) or not req[key]: raise ResidentQwenError(f"request field {key} is required")
        stage = str(req["stage"])
        route = None
        params = req.get("parameters") or {}
        self._request_tensor_names = params.get("tensor_names", {}) if isinstance(params, Mapping) else {}
        if req["source_sha256"] != self.source_sha256: raise ResidentQwenError("request source identity does not match model")
        if req["stage"] not in _STAGES: raise ResidentQwenError(f"unsupported Qwen stage {req['stage']!r}")
        if isinstance(req.get("token"), bool) or not isinstance(req.get("token"), int) or req["token"] < 0: raise ResidentQwenError("token must be a nonnegative integer")
        if isinstance(req.get("position"), bool) or not isinstance(req.get("position"), int) or req["position"] < 0: raise ResidentQwenError("position must be a nonnegative integer")
        layer = req.get("layer")
        if req["stage"] in {
            "qwen-attention",
            "qwen-ffn",
            "qwen-route",
            "qwen-experts",
            "qwen-layer",
            "qwen-attention-route",
        } and (isinstance(layer, bool) or not isinstance(layer, int) or layer < 0):
            raise ResidentQwenError("layer is required for attention/FFN/route/expert stages")
        if layer is not None and (isinstance(layer, bool) or not isinstance(layer, int) or layer < 0): raise ResidentQwenError("layer must be a nonnegative integer or null")
        supplied_request_digest = req.get("request_sha256")
        unsigned_request = dict(req)
        unsigned_request.pop("request_sha256", None)
        computed_request_digest = hashlib.sha256(
            canonical_json_bytes(unsigned_request)
        ).hexdigest()
        if (
            supplied_request_digest is not None
            and supplied_request_digest != computed_request_digest
        ):
            raise ResidentQwenError("request digest does not match request content")
        request_digest = supplied_request_digest or computed_request_digest
        arrays, _ = self._load_state(req)
        graph_receipt = None
        token = eog = None
        if stage == "qwen-embedding":
            arrays, snapshot = self._embedding(req, arrays)
        elif stage == "qwen-attention":
            arrays, snapshot = self._attention(req, arrays)
        elif stage in {"qwen-layer", "qwen-attention-route"}:
            if stage == "qwen-layer" and self.architecture != "qwen35":
                raise ResidentQwenError("qwen-layer is unsupported for MoE qwen35")
            if stage == "qwen-attention-route" and self.architecture != "qwen35moe":
                raise ResidentQwenError("qwen-attention-route is unsupported for dense qwen35")
            # Dense layers run attention and FFN in one stage; the graph site
            # covers the attention subgraph that precedes the FFN either way.
            graph_capture: dict[str, Any] = {}
            arrays, _ = self._attention(
                req, arrays, persist=False, graph_capture=graph_capture,
            )
            specialist = graph_capture.get("binding", {}).get("specialist")
            graph_receipt = (
                self._recurrent_graph_receipt(graph_capture)
                if specialist == "recurrent-dynamics"
                else self._attention_memory_receipt(graph_capture)
                if specialist == "attention-memory"
                else None
            )
            if stage == "qwen-attention-route":
                parameters = dict(req.get("parameters") or {})
                parameters["route_only"] = True
                req = dict(req)
                req["parameters"] = parameters
            arrays, snapshot, route = self._ffn(req, arrays)
        elif stage in {"qwen-ffn", "qwen-route", "qwen-experts"}:
            if stage in {"qwen-route", "qwen-experts"} and self.architecture != "qwen35moe":
                raise ResidentQwenError(f"{stage} is unsupported for dense qwen35")
            parameters = dict(req.get("parameters") or {})
            if stage == "qwen-route":
                parameters["route_only"] = True
            elif stage == "qwen-experts":
                if "expert_ids" not in parameters and "router_ids" in arrays:
                    parameters["expert_ids"] = [int(i) for i in arrays["router_ids"].reshape(-1)]
                parameters["route_only"] = False
            req = dict(req); req["parameters"] = parameters
            arrays, snapshot, route = self._ffn(req, arrays)
        else:
            arrays, snapshot, token, eog, graph_receipt = self._head(req, arrays)
        result: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "operation_id": req["operation_id"],
            "source_sha256": self.source_sha256,
            "stage": stage,
            "layer": layer,
            "position": req["position"],
            "snapshot": _plain(snapshot),
            "request_sha256": request_digest,
            "executor": EXECUTOR_ID,
            "backend": self.backend,
            "logical_weight_bytes": self._logical_weight_bytes,
        }
        if route is not None:
            observation = route.pop("expert_observation", None)
            if isinstance(observation, Mapping):
                result["expert_observation"] = _plain(observation)
            graph_training = route.pop("graph_site_training", None)
            graph_observation = route.pop("graph_site_observation", None)
            graph_abstention = route.pop("graph_site_abstention", None)
            if isinstance(graph_training, Mapping):
                result["graph_site_training"] = _plain(graph_training)
            if isinstance(graph_observation, Mapping):
                result["graph_site_observation"] = _plain(graph_observation)
            if isinstance(graph_abstention, Mapping):
                result["graph_site_abstention"] = _plain(graph_abstention)
            if "native_ops_omitted" in route:
                result["native_ops_omitted"] = int(route["native_ops_omitted"])
            result["expert_route"] = _plain(route)
        if isinstance(graph_receipt, Mapping):
            result.update(_plain(graph_receipt))
            if "graph_site_training" in graph_receipt:
                result["native_ops_omitted"] = 0
            if isinstance(graph_receipt.get("graph_site_observation"), Mapping):
                result["native_ops_omitted"] = int(
                    graph_receipt["graph_site_observation"].get("native_ops_omitted", 0)
                )
        if token is not None: result["token"] = token; result["eog"] = bool(eog)
        canonical_json_bytes(result)
        return result

    def tokenize(self, text: str, add_special: bool = False) -> list[int]:
        if not isinstance(text, str): raise ResidentQwenError("text must be a string")
        if self._tokenizer is not None:
            try:
                return [int(t) for t in self._tokenizer.encode(text, add_special=add_special)]
            except (TypeError, ValueError) as exc:
                raise ResidentQwenError("GGUF tokenizer rejected text") from exc
        tokens = self._model.metadata.get("tokenizer.ggml.tokens", [])
        if not isinstance(tokens, list) or not tokens: raise ResidentQwenError("GGUF tokenizer vocabulary is unavailable")
        # Greedy longest token matching is exact for already-tokenized fixture text
        # and preserves byte tokens for ordinary Qwen BPE pieces.
        table = {str(v): i for i, v in enumerate(tokens)}
        out: list[int] = []; i = 0
        while i < len(text):
            match = max((piece for piece in table if text.startswith(piece, i)), key=len, default=None)
            if match is None:
                match = text[i];
            out.append(table.get(match, int(self._meta("tokenizer.ggml.unknown_token_id", 0)))); i += len(match)
        if add_special and bool(self._meta("tokenizer.ggml.add_bos_token", False)):
            bos = self._meta("tokenizer.ggml.bos_token_id");
            if bos is not None: out.insert(0, int(bos))
        if add_special and bool(self._meta("tokenizer.ggml.add_eos_token", False)):
            eos = self._meta("tokenizer.ggml.eos_token_id");
            if eos is not None: out.append(int(eos))
        return out

    def detokenize(self, tokens: Sequence[int]) -> str:
        if self._tokenizer is not None:
            try:
                return str(self._tokenizer.decode([int(t) for t in tokens]))
            except (TypeError, ValueError) as exc:
                raise ResidentQwenError("GGUF tokenizer rejected token sequence") from exc
        table = self._model.metadata.get("tokenizer.ggml.tokens", [])
        if not isinstance(table, list): raise ResidentQwenError("GGUF tokenizer vocabulary is unavailable")
        pieces = []
        for token in tokens:
            if isinstance(token, bool) or not isinstance(token, int) or token < 0 or token >= len(table): raise ResidentQwenError("token is outside vocabulary")
            pieces.append(str(table[token]))
        return "".join(pieces).replace("Ġ", " ")

    def is_quiescent(self) -> bool:
        with self._stage_transaction_guard:
            has_stage_transactions = bool(self._stage_transactions)
        return (
            not self._closed
            and self._activation_exchange is None
            and self._device_epoch is None
            and not has_stage_transactions
            and not self._visual_embedding_sets
            and not self._volatile_visual_previous
            and not self._volatile_visual_snapshots
            and not self._volatile_visual_checkpoints
        )

    def handoff_visual_encoder(self, successor: "ResidentQwenExecutor") -> None:
        if not self.is_quiescent() or successor.source_sha256 != self.source_sha256:
            raise ResidentQwenError("visual encoder handoff requires quiescent matching banks")
        if self._vision_encoder is not None:
            successor.bind_visual_encoder(self._vision_encoder)
            self._vision_encoder = None

    def close(self) -> None:
        with self._stage_transaction_guard:
            open_tickets = tuple(self._stage_transactions)
        for ticket in open_tickets:
            self.abort_stage_transaction(ticket)
        if not self._closed:
            self._volatile_visual_previous.clear()
            self._working_snapshot = None
            self._working_arrays = None
            self._working_metadata = None
            self._bank.close()
            self._closed = True
            self._volatile_visual_checkpoints.clear()
            self._visual_embedding_sets.clear()
            self._volatile_visual_snapshots.clear()
            if self._vision_encoder is not None:
                close_visual = getattr(self._vision_encoder, "close", None)
                if callable(close_visual):
                    close_visual()
                self._vision_encoder = None


__all__ = [
    "VISUAL_STAGE_REQUEST_SCHEMA",
    "VISUAL_STAGE_RESULT_SCHEMA",
    "EXECUTOR_ID",
    "NEURAL_MEMBRANE_SITE_KINDS",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "ResidentQwenError",
    "ResidentQwenExecutor",
    "stage_dispatch_priority",
]
