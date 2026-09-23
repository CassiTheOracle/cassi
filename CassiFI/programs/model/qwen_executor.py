"""Field-scheduled, single-stage Qwen3.5 resident executor.

This module deliberately does not depend on the llama inference API.  It owns
one numerical stage per call; token progression and stage ordering remain in
the field program.  Quantized model weights are supplied by ``WeightBank`` and
all mutable activations are committed as immutable snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, MutableMapping, Sequence

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

REQUEST_SCHEMA = "cassifi.resident-model-stage-request.v1"
RESULT_SCHEMA = "cassifi.resident-model-stage-result.v1"
EXECUTOR_ID = "cassi-resident-qwen"
_ARCHITECTURES = {"qwen35", "qwen35moe"}
NEURAL_MEMBRANE_SITE_KINDS = frozenset(
    {
        "embedding",
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


def _finite_array(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 0 or not np.all(np.isfinite(arr)):
        raise ResidentQwenError(f"{name} must be a finite non-scalar array")
    return np.ascontiguousarray(arr, dtype=np.float32)


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


def _silu(x: np.ndarray) -> np.ndarray:
    return x * np.asarray(_sigmoid(x), dtype=np.float32)


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
    ) -> Mapping[str, Any]:
        del reuse_immutable_arrays
        clean = {str(k): _finite_array(v, name=str(k)) for k, v in arrays.items()}
        body = {
            "schema": "cassifi.resident-snapshot.inline.v1",
            "metadata": _plain(metadata),
            "arrays": {k: {"shape": list(v.shape), "dtype": "float32", "values": v.tolist()} for k, v in sorted(clean.items())},
        }
        digest = digest_value(body)
        return {"schema": body["schema"], "snapshot_sha256": digest, "metadata": body["metadata"], "arrays": body["arrays"]}

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

    def close(self) -> None:
        return None


class ResidentQwenExecutor:
    """Execute exactly one field-selected Qwen3.5 stage per invocation."""

    def __init__(self, model_path: str | Path | Mapping[str, Any], state_directory: str | Path, *, backend: str = "cpu", library_path: str | Path | None = None, threads: int = 8, manifest: Mapping[str, Any] | None = None):
        self.backend = str(backend)
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
        self._activation_exchange: Callable[[str, np.ndarray], np.ndarray] | None = None
        self._device_epoch: Any | None = None
        self._device_membrane: Any | None = None
        self._validate_metadata()

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

    @staticmethod
    def _neural_site(
        kind: str,
        *,
        head: int | None = None,
        layer: int | None = None,
        expert: int | None = None,
    ) -> str:
        if kind not in NEURAL_MEMBRANE_SITE_KINDS:
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

        if kind not in NEURAL_MEMBRANE_SITE_KINDS:
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
        if isinstance(self._bank, _ArrayBank):
            return np.asarray(self._bank.tensors[name], dtype=np.float32)
        method = getattr(self._bank, "tensor", None)
        if method is None:
            raise ResidentQwenError("WeightBank.tensor is required for rank>1 recurrent convolution tensors")
        return np.asarray(method(name), dtype=np.float32)

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
        if (
            self._working_snapshot is not None
            and self._working_arrays is not None
            and self._working_metadata is not None
            and plain_descriptor == self._working_snapshot
        ):
            self.working_snapshot_hits += 1
            return dict(self._working_arrays), dict(self._working_metadata)
        arrays, metadata = self._snapshots.load(descriptor)
        if metadata.get("source_sha256", self.source_sha256) != self.source_sha256:
            raise ResidentQwenError("snapshot source identity does not match executor model")
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
                prepared[name] = _finite_array(value, name=name)
        for array in prepared.values():
            array.setflags(write=False)
        descriptor = self._snapshots.save(
            prepared,
            metadata,
            reuse_immutable_arrays=True,
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

    def _rope(self, x: np.ndarray, position: int | Sequence[int], sections: Sequence[int] | None, base: float) -> np.ndarray:
        y = x.copy()
        if sections is None:
            sections = [x.size]
        pos = list(position) if isinstance(position, Sequence) and not isinstance(position, (str, bytes)) else [int(position)]
        offset = 0
        for si, raw_n in enumerate(sections):
            n = int(raw_n)
            if n <= 0:
                continue
            p = float(pos[min(si, len(pos) - 1)])
            for i in range(0, min(n, x.size - offset) - 1, 2):
                theta = p * (base ** (-2.0 * (i // 2) / max(1, n)))
                c, s = math.cos(theta), math.sin(theta)
                a, b = y[offset + i], y[offset + i + 1]
                y[offset + i], y[offset + i + 1] = np.float32(a * c - b * s), np.float32(a * s + b * c)
            offset += n
            if offset >= x.size:
                break
        return y

    def _embedding(self, request: Mapping[str, Any], arrays: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
        token = int(request["token"])
        name = self._weight("token_embd", required=True)
        expected = int(self._meta(f"{self.architecture}.embedding_length", self._meta("embedding_length", 0)))
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

    def _full_attention(self, x: np.ndarray, arrays: dict[str, np.ndarray], layer: int, position: int) -> np.ndarray:
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
                query_gate, q = q[nh * hd_meta:], q[:nh * hd_meta]
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
            scores = (keys[:, h % nk, :] @ qh[h]) * scale
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
            context[h] = probabilities @ vals[:, h % nk, :]
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
        position: int,
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
        qkv_name = self._weight("attn_qkv", layer, required=False)
        if qkv_name is None:
            names = tuple(self._weight(stem, layer) for stem in ("attn_q", "attn_k", "attn_v"))
            q, k, v = epoch.matvec_many(names, y)
            if hd_meta > 0 and q.count == 2 * nh * hd_meta:
                gate = epoch.view(q, nh * hd_meta, nh * hd_meta)
                q = epoch.view(q, 0, nh * hd_meta)
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
        q_heads = [
            epoch.rope(epoch.view(q, head * hd, hd), position, sections, base)
            for head in range(nh)
        ]
        k_heads = [
            epoch.rope(epoch.view(k, head * hd, hd), position, sections, base)
            for head in range(nk)
        ]
        def join_heads(heads: list[Any]) -> Any:
            result = heads[0]
            for item in heads[1:]:
                result = epoch.concat(result, item)
            return result
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
            scores = epoch.attention_scores(
                epoch.view(q, head * hd, hd), keys, head % nk, nk, hd,
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
                epoch.attention_context(probabilities, vals, head % nk, nk, vd)
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

    def _recurrent_attention(self, x: np.ndarray, arrays: dict[str, np.ndarray], layer: int, position: int) -> np.ndarray:
        """Run one Qwen3.5 gated-delta recurrent attention token."""
        y = self._norm(x, "attn_norm", layer)
        y = self._exchange("attention.normalized", y, layer=layer)
        qkv_mixed, z_gate = self._mat_many(
            (("attn_qkv", None), ("attn_gate", None)),
            y,
            layer,
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
        history = arrays.get(
            history_name,
            np.empty((0, raw_qkv.size), dtype=np.float32),
        ).reshape(-1, raw_qkv.size)
        next_history = self._exchange(
            "recurrent.conv-history",
            np.concatenate([history, raw_qkv[None, :]], axis=0),
            layer=layer,
        )
        conv_name = self._weight("ssm_conv1d", layer, required=False)
        convolved = next_history[-1]
        if conv_name is not None:
            kernel = self._tensor(conv_name).reshape(raw_qkv.size, -1)
            kernel_size = kernel.shape[1]
            taps = next_history[-kernel_size:]
            newest_first = taps[::-1]
            # At the beginning of a sequence the absent older taps are zeros.
            # Pair only the available current-to-oldest values with the same
            # leading kernel coefficients instead of requiring a full window.
            convolved = np.sum(
                newest_first * kernel.T[: newest_first.shape[0]],
                axis=0,
                dtype=np.float32,
            )
        arrays[history_name] = next_history
        qkv_mixed = self._exchange(
            "recurrent.convolved-qkv",
            convolved,
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
            out[h] = state[h] @ q[h % nk]
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
        proj = self._mat("ssm_out", out.reshape(-1), layer, required=False)
        if proj is None:
            proj = self._mat("attn_out", out.reshape(-1), layer)
        assert proj is not None
        return self._exchange("recurrent.projected", proj, layer=layer)

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
        prior = arrays.get(f"conv_history.{layer}")
        history = (
            epoch.concat(epoch.upload(prior.reshape(-1)), raw)
            if prior is not None and prior.size else raw
        )
        history = self._exchange_device("recurrent.conv-history", history, layer=layer)
        conv_name = self._weight("ssm_conv1d", layer, required=False)
        convolved = (
            epoch.recurrent_conv(history, conv_name, channels=qkv.count)
            if conv_name is not None
            else epoch.view(history, history.count - qkv.count, qkv.count)
        )
        convolved = self._exchange_device("recurrent.convolved-qkv", convolved, layer=layer)
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
            epoch.recurrent_readout(state, q, nv, nk, value_dim, key_dim),
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
    ) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
        layer = int(request["layer"])
        position = int(request["position"])
        x = arrays.get("hidden")
        arrays.pop("router_ids", None)
        arrays.pop("router_weights", None)
        if x is None:
            raise ResidentQwenError("attention stage requires hidden in snapshot")
        interval = int(self._meta(f"{self.architecture}.full_attention_interval", self._meta("full_attention_interval", 4)))
        recurrent = bool((request.get("parameters") or {}).get("recurrent", interval > 0 and (layer + 1) % interval != 0))
        if self._device_epoch is not None:
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
                arrays[f"conv_history.{layer}"] = history_host.reshape(-1, channel_count)
                arrays[f"recurrent_state.{layer}"] = state_host.reshape(nv, value_dim, key_dim)
            else:
                out, keys, vals, nk, head_dim, value_dim = (
                    self._full_attention_device(device_x, arrays, layer, position)
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
        out = self._recurrent_attention(x, arrays, layer, position) if recurrent else self._full_attention(x, arrays, layer, position)
        arrays["attention_residual"] = x.copy()
        arrays["hidden"] = np.asarray(out, dtype=np.float32)
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
            # Keep route and its exact normalized input in the immutable
            # snapshot so the policy can select/evict before expert execution.
            arrays["ffn_input"] = y
            arrays["router_logits"] = router
            arrays["router_probabilities"] = probs
            arrays["router_ids"] = ids.astype(np.float32)
            if bool(params.get("route_only", False)):
                return arrays, self._save_state(arrays, request), route
            prefetch = getattr(self._bank, "prefetch", None)
            residency = getattr(self._bank, "residency", None)
            prefetch_ids = params.get("prefetch_experts", selected_ids)
            if not isinstance(prefetch_ids, Sequence) or isinstance(prefetch_ids, (str, bytes)):
                raise ResidentQwenError("parameters.prefetch_experts must be a sequence")
            prefetch_started_ns = time.perf_counter_ns()
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
                        epoch.scale(shared_down, float(epoch.download(selector)[0])),
                        layer=layer,
                    )
                    device_result = epoch.add(device_result, shared_weighted)
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
        result = self._exchange("ffn.output", result, layer=layer)
        arrays["hidden"] = self._exchange(
            "layer.output",
            residual + result,
            layer=layer,
        )
        arrays.pop("attention_residual", None)
        return arrays, self._save_state(arrays, request), route

    def _head(
        self,
        request: Mapping[str, Any],
        arrays: dict[str, np.ndarray],
    ) -> tuple[dict[str, np.ndarray], Mapping[str, Any], int | None, bool]:
        x = arrays.get("hidden")
        if x is None:
            raise ResidentQwenError("head stage requires hidden in snapshot")
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
                return arrays, _plain(dict(snapshot)), None, False
            arrays.pop("logits", None)
            return arrays, self._save_state(arrays, request), None, False
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
        else:
            x = self._exchange("head.input", x.reshape(-1))
            y = self._norm(x, "output_norm", None)
            y = self._exchange("head.normalized", y)
            logits = self._mat("output", y, None)
            if logits is None:
                raise ResidentQwenError("output projection is absent")
            logits = self._exchange("head.logits", logits)
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
        eos = self._meta("tokenizer.ggml.eos_token_id", None)
        return (
            arrays,
            self._save_state(arrays, request),
            token,
            eos is not None and token == int(eos),
        )

    def execute_stage(
        self,
        request: Mapping[str, Any],
        *,
        activation_exchange: Callable[[str, np.ndarray], np.ndarray] | None = None,
    ) -> Mapping[str, Any]:
        """Execute one stage with an optional owner-field membrane epoch."""

        if activation_exchange is not None and not callable(activation_exchange):
            raise ResidentQwenError("activation_exchange must be callable")
        if self._activation_exchange is not None:
            raise ResidentQwenError("resident executor does not permit nested stages")
        self._activation_exchange = activation_exchange
        try:
            if (
                activation_exchange is not None
                and WeightBank is not None
                and isinstance(self._bank, WeightBank)
                and self.backend == "vulkan"
            ):
                membrane = getattr(activation_exchange, "__self__", None)
                if membrane is None or not callable(getattr(membrane, "bind_device", None)):
                    raise ResidentQwenError("Vulkan neural exchange requires an owner membrane epoch")
                self._device_membrane = membrane
                self._device_epoch = membrane.bind_device(self._bank)
            return self._execute_stage(request)
        finally:
            self._activation_exchange = None
            self._device_epoch = None
            self._device_membrane = None

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
        token = eog = None
        if stage == "qwen-embedding":
            arrays, snapshot = self._embedding(req, arrays)
        elif stage == "qwen-attention":
            arrays, snapshot = self._attention(req, arrays)
        elif stage == "qwen-layer":
            if self.architecture != "qwen35":
                raise ResidentQwenError("qwen-layer is unsupported for MoE qwen35")
            arrays, _ = self._attention(req, arrays, persist=False)
            arrays, snapshot, route = self._ffn(req, arrays)
        elif stage == "qwen-attention-route":
            if self.architecture != "qwen35moe":
                raise ResidentQwenError("qwen-attention-route is unsupported for dense qwen35")
            arrays, _ = self._attention(req, arrays, persist=False)
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
            arrays, snapshot, token, eog = self._head(req, arrays)
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
            result["expert_route"] = _plain(route)
            if isinstance(observation, Mapping):
                result["expert_observation"] = _plain(observation)
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

    def close(self) -> None:
        if not self._closed:
            self._working_snapshot = None
            self._working_arrays = None
            self._working_metadata = None
            self._bank.close()
            self._closed = True


__all__ = [
    "EXECUTOR_ID",
    "NEURAL_MEMBRANE_SITE_KINDS",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "ResidentQwenError",
    "ResidentQwenExecutor",
]
