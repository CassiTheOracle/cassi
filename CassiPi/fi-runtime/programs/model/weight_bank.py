"""Field-owned GGUF weight access through the CassiFI native C ABI.

This module intentionally binds only ``cassifi-weight-bank``.  It never loads
llama.cpp (or discovers a library through PATH): the numerical implementation
is a small, separately built C ABI and the field graph remains responsible for
scheduling model stages.
"""
from __future__ import annotations

import ctypes
import os
import re
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .gguf import inspect_gguf, reuse_verified_manifest


class WeightBankError(RuntimeError):
    """A weight bank could not be opened or an operation failed."""


class _TensorInfo(ctypes.Structure):
    _fields_ = [
        ("rank", ctypes.c_uint32),
        ("dims", ctypes.c_int64 * 4),
        ("ggml_type", ctypes.c_int32),
        ("element_count", ctypes.c_uint64),
        ("byte_size", ctypes.c_uint64),
    ]


# The full native ABI that any usable weight-bank library must export.
# Implicit discovery skips stale builds, while explicit paths fail with the
# missing-symbol list during binding. Field previews require the snapshot ABI.
_REQUIRED_SYMBOLS = (
    "cassifi_weight_bank_load",
    "cassifi_weight_bank_close",
    "cassifi_weight_bank_last_error",
    "cassifi_weight_bank_tensor_info",
    "cassifi_weight_bank_read_vector",
    "cassifi_weight_bank_read_embedding",
    "cassifi_weight_bank_matvec",
    "cassifi_weight_bank_matvec_batch",
    "cassifi_weight_bank_device_epoch_snapshot",
)

# The only paths used for implicit discovery. A caller may pass an explicit
# library_path (or CASSIFI_WEIGHT_BANK_LIBRARY), but even that path must name
# this library and must not be llama.dll. The isolated recurrent build can
# remain usable while an older resident DLL is held open by another process.
_LIBRARY_BASENAMES = (
    "cassifi-weight-bank.dll",
    "cassifi_weight_bank.dll",
    "libcassifi-weight-bank.dll",
    "libcassifi_weight_bank.dll",
    "libcassifi-weight-bank.so",
    "libcassifi_weight_bank.so",
    "libcassifi-weight-bank.dylib",
    "libcassifi_weight_bank.dylib",
)


def _library_is_allowed(path: Path) -> bool:
    name = path.name.lower()
    if "llama" in name or name not in {item.lower() for item in _LIBRARY_BASENAMES}:
        return False
    return path.is_file()


def _library_candidates() -> list[Path]:
    # This file is root/CassiFI/programs/model/weight_bank.py.
    cassifi_root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = []
    runtime = cassifi_root / "native" / "field-runtime"
    for build in (runtime / "build-recurrent", runtime / "build-resident", runtime / "build"):
        for directory in (build / "Release", build, build / "Debug"):
            for basename in _LIBRARY_BASENAMES:
                candidate = directory / basename
                if candidate not in candidates:
                    candidates.append(candidate)
    return candidates


# Loaded native libraries, keyed by absolute path.  Loading the same DLL once
# per process keeps the OS loader from duplicating it and lets repeated
# WeightBank/vulkan_memory constructions skip repeat work.
_LOADED_LIBRARIES: dict[str, ctypes.CDLL] = {}
# First implicitly resolved library that passed ABI verification.  Implicit
# discovery is not repeated per construction in hot stages.
_VERIFIED_IMPLICIT_LIBRARY: Path | None = None


def _acquire_library(path: Path) -> ctypes.CDLL:
    """Load the native library at ``path`` once and cache the handle."""
    key = str(path)
    cached = _LOADED_LIBRARIES.get(key)
    if cached is not None:
        return cached
    try:
        library = ctypes.CDLL(key)
    except OSError as exc:
        raise WeightBankError(f"cannot load cassifi-weight-bank {path}: {exc}") from exc
    _LOADED_LIBRARIES[key] = library
    return library


def _library_exports_required_abi(library: ctypes.CDLL) -> list[str]:
    return [name for name in _REQUIRED_SYMBOLS if not hasattr(library, name)]


def _resolve_library(library_path: str | os.PathLike[str] | None) -> Path:
    requested = library_path
    if requested is None:
        env_path = os.environ.get("CASSIFI_WEIGHT_BANK_LIBRARY")
        requested = env_path if env_path else None
    if requested is not None:
        path = Path(requested).expanduser().resolve()
        if not _library_is_allowed(path):
            raise WeightBankError(
                "explicit native library must be an existing cassifi-weight-bank "
                "library (llama.dll is never accepted)"
            )
        return path
    global _VERIFIED_IMPLICIT_LIBRARY
    verified = _VERIFIED_IMPLICIT_LIBRARY
    if verified is not None:
        return verified
    rejected: list[str] = []
    for candidate in _library_candidates():
        if not _library_is_allowed(candidate):
            continue
        try:
            library = _acquire_library(candidate)
        except WeightBankError:
            rejected.append(str(candidate))
            continue
        if _library_exports_required_abi(library):
            rejected.append(str(candidate))
            continue
        _VERIFIED_IMPLICIT_LIBRARY = candidate
        return candidate
    searched = ", ".join(str(path) for path in _library_candidates())
    raise WeightBankError(
        "cassifi-weight-bank native library is unavailable (candidates missing "
        "required ABI symbols such as cassifi_weight_bank_matvec_batch are "
        "rejected); searched only " + searched
    )


def _as_c_string(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise WeightBankError(f"{label} must be non-empty text")
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WeightBankError(f"{label} is not valid UTF-8") from exc


def vulkan_memory(
    library_path: str | os.PathLike[str] | None = None,
) -> tuple[int, int]:
    """Query the same Vulkan device (index zero) used by the weight bank."""
    library = _acquire_library(_resolve_library(library_path))
    query = getattr(library, "cassifi_weight_bank_vulkan_memory", None)
    if query is None:
        raise WeightBankError("native weight bank has no Vulkan memory query")
    query.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    query.restype = ctypes.c_int
    free = ctypes.c_size_t()
    total = ctypes.c_size_t()
    result = query(ctypes.byref(free), ctypes.byref(total))
    if result != 0 or not total.value or free.value > total.value:
        raise WeightBankError(f"Vulkan memory query unavailable (error {result})")
    return int(free.value), int(total.value)


class WeightBank:
    """Read GGUF tensors through the independently built weight-bank ABI.

    ``WeightBank`` owns no graph, activation, sampler, or adaptive state.  A
    native handle is held only for immutable GGUF weight access and can be
    closed repeatedly.  Inputs that are already contiguous float32 arrays are
    passed to the ABI without a conversion or copy.
    """

    def __init__(
        self,
        model_path: str | os.PathLike[str],
        *,
        backend: str = "cpu",
        library_path: str | os.PathLike[str] | None = None,
        threads: int = 8,
        manifest: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(backend, str) or not backend:
            raise WeightBankError("backend must be non-empty text")
        if isinstance(threads, bool) or not isinstance(threads, int) or threads <= 0:
            raise WeightBankError("threads must be a positive integer")
        path = Path(model_path).expanduser().resolve()
        if not path.is_file():
            raise WeightBankError(f"GGUF model is not a regular file: {path}")
        try:
            # A supplied manifest is reusable only when this process already
            # hashed it and the source's stat identity has not changed.
            manifest = (
                dict(reuse_verified_manifest(path, manifest))
                if manifest is not None
                else inspect_gguf(path)
            )
        except Exception as exc:
            raise WeightBankError(f"cannot verify GGUF model {path}: {exc}") from exc

        native_path = _resolve_library(library_path)
        library = _acquire_library(native_path)
        self._bind(library)
        self._library = library
        self._handle: ctypes.c_void_p | None = None
        self.model_path = path
        self.backend = backend
        self.threads = threads
        self.source_id = str(manifest.get("source_id", path.name))
        self.source_sha256 = str(manifest["source_sha256"])
        self.manifest = manifest
        self._device_epochs: set[DeviceEpoch] = set()
        handle = ctypes.c_void_p()
        result = self._load(
            _as_c_string(str(path), "model_path"),
            _as_c_string(backend, "backend"),
            ctypes.c_int32(threads),
            ctypes.byref(handle),
        )
        if result != 0 or not handle.value:
            # A null handle has no usable last_error, so retain the ABI result
            # and avoid leaking a partially returned context.
            message = f"native weight-bank load failed (error {result})"
            if handle.value:
                try:
                    message = self._native_error(handle) or message
                    self._close(handle)
                except Exception:
                    pass
            raise WeightBankError(message)
        self._handle = handle

    def _bind(self, library: ctypes.CDLL) -> None:
        missing = [name for name in _REQUIRED_SYMBOLS if not hasattr(library, name)]
        if missing:
            raise WeightBankError("native library is missing ABI symbols: " + ", ".join(missing))
        self._load = library.cassifi_weight_bank_load
        self._load.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]
        self._load.restype = ctypes.c_int
        self._close = library.cassifi_weight_bank_close
        self._close.argtypes = [ctypes.c_void_p]
        self._close.restype = None
        self._last_error = library.cassifi_weight_bank_last_error
        self._last_error.argtypes = [ctypes.c_void_p]
        self._last_error.restype = ctypes.c_char_p
        self._tensor_info = library.cassifi_weight_bank_tensor_info
        self._tensor_info.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(_TensorInfo)]
        self._tensor_info.restype = ctypes.c_int
        self._read_vector = library.cassifi_weight_bank_read_vector
        self._read_vector.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._read_vector.restype = ctypes.c_int
        self._read_embedding = library.cassifi_weight_bank_read_embedding
        self._read_embedding.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._read_embedding.restype = ctypes.c_int
        self._matvec = library.cassifi_weight_bank_matvec
        self._matvec.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_int32,
        ]
        self._matvec_batch = library.cassifi_weight_bank_matvec_batch
        self._matvec_batch.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_int32,
        ]
        self._matvec_batch.restype = ctypes.c_int

        self._matvec_batch_experts = getattr(
            library, "cassifi_weight_bank_matvec_batch_experts", None
        )
        if self._matvec_batch_experts is not None:
            self._matvec_batch_experts.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._matvec_batch_experts.restype = ctypes.c_int
        self._matvec_many = getattr(library, "cassifi_weight_bank_matvec_many", None)
        if self._matvec_many is not None:
            self._matvec_many.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_char_p),
                ctypes.POINTER(ctypes.c_int32),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._matvec_many.restype = ctypes.c_int
        self._read_tensor_f32 = getattr(library, "cassifi_weight_bank_read_tensor_f32", None)
        if self._read_tensor_f32 is not None:
            self._read_tensor_f32.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self._read_tensor_f32.restype = ctypes.c_int

        self._prefetch = getattr(library, "cassifi_weight_bank_prefetch", None)
        self._evict = getattr(library, "cassifi_weight_bank_evict", None)
        self._residency = getattr(library, "cassifi_weight_bank_residency", None)
        for function in (self._prefetch, self._evict):
            if function is not None:
                function.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32]
                function.restype = ctypes.c_int
        if self._residency is not None:
            self._residency.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_int32),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
            ]
            self._residency.restype = ctypes.c_int
        device_abi = {
            "epoch_begin": (
                "cassifi_weight_bank_device_epoch_begin",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                 ctypes.c_size_t, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)],
            ),
            "epoch_finish": (
                "cassifi_weight_bank_device_epoch_finish",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_size_t)],
            ),
            "epoch_close": ("cassifi_weight_bank_device_epoch_close", [ctypes.c_void_p]),
            "upload": (
                "cassifi_weight_bank_device_tensor_upload",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "view": (
                "cassifi_weight_bank_device_tensor_view",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "count": (
                "cassifi_weight_bank_device_tensor_count",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)],
            ),
            "download": (
                "cassifi_weight_bank_device_tensor_download",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float),
                 ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)],
            ),
            "download_many": (
                "cassifi_weight_bank_device_tensor_download_many",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t),
                 ctypes.POINTER(ctypes.c_size_t)],
            ),
            "release": ("cassifi_weight_bank_device_tensor_release", [ctypes.c_void_p]),
            "release_many": (
                "cassifi_weight_bank_device_tensor_release_many",
                [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t],
            ),
            "matvec": (
                "cassifi_weight_bank_device_matvec",
                [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int32,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "matvec_many": (
                "cassifi_weight_bank_device_matvec_many",
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p),
                 ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t, ctypes.c_void_p,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "low_rank_affine": (
                "cassifi_weight_bank_device_low_rank_affine",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p,
                 ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_float), ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_void_p)],
            ),
            "exchange": (
                "cassifi_weight_bank_device_exchange",
                [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
                 ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
                 ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)],
            ),
            "silu": ("cassifi_weight_bank_device_silu",
                     [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]),
            "sigmoid": ("cassifi_weight_bank_device_sigmoid",
                        [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]),
            "scale": ("cassifi_weight_bank_device_scale",
                      [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float,
                       ctypes.POINTER(ctypes.c_void_p)]),
            "mul": ("cassifi_weight_bank_device_mul",
                    [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                     ctypes.POINTER(ctypes.c_void_p)]),
            "add": ("cassifi_weight_bank_device_add",
                    [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                     ctypes.POINTER(ctypes.c_void_p)]),
            "embedding": (
                "cassifi_weight_bank_device_embedding",
                [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint64,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "concat": (
                "cassifi_weight_bank_device_concat",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "norm_rows": (
                "cassifi_weight_bank_device_norm_rows",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_float,
                 ctypes.c_int32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)],
            ),
            "mul_rows": (
                "cassifi_weight_bank_device_mul_rows",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "exp_clipped": (
                "cassifi_weight_bank_device_exp_clipped",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "softplus": (
                "cassifi_weight_bank_device_softplus",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
            ),
            "softmax": (
                "cassifi_weight_bank_device_softmax",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
            ),
            "positive_normalize": (
                "cassifi_weight_bank_device_positive_normalize",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
            ),
            "recurrent_conv": (
                "cassifi_weight_bank_device_recurrent_conv",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "recurrent_predict": (
                "cassifi_weight_bank_device_recurrent_predict",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                 ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "recurrent_update": (
                "cassifi_weight_bank_device_recurrent_update",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                 ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "recurrent_readout": (
                "cassifi_weight_bank_device_recurrent_readout",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                 ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "rope": (
                "cassifi_weight_bank_device_rope",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64,
                 ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t, ctypes.c_double,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "attention_scores": (
                "cassifi_weight_bank_device_attention_scores",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                 ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_float,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
            "attention_context": (
                "cassifi_weight_bank_device_attention_context",
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                 ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t,
                 ctypes.POINTER(ctypes.c_void_p)],
            ),
        }
        self._device = {}
        for name, (symbol, argtypes) in device_abi.items():
            function = getattr(library, symbol, None)
            if function is None:
                self._device.clear()
                break
            function.argtypes = argtypes
            function.restype = None if name in {"epoch_close", "release"} else ctypes.c_int
            self._device[name] = function
        snapshot = getattr(library, "cassifi_weight_bank_device_epoch_snapshot", None)
        if snapshot is not None and self._device:
            snapshot.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            snapshot.restype = ctypes.c_int
            self._device["epoch_snapshot"] = snapshot

    def _require_open(self) -> ctypes.c_void_p:
        handle = self._handle
        if handle is None or not handle.value:
            raise WeightBankError("weight bank is closed")
        return handle

    def _native_error(self, handle: ctypes.c_void_p | None = None) -> str:
        selected = handle if handle is not None else self._handle
        if selected is None or not selected.value:
            return ""
        try:
            raw = self._last_error(selected)
            return raw.decode("utf-8", "replace") if raw else ""
        except Exception:
            return ""

    def _check(self, result: int, operation: str) -> None:
        if result:
            detail = self._native_error()
            if result == -8:
                match = re.search(r"requested_bytes~=(\d+) free_bytes=(\d+)", detail)
                if match is not None:
                    from cassi_field_residency import ResourceWait
                    raise ResourceWait(
                        "vram", int(match.group(1)), int(match.group(2)),
                        kind="scratch" if "workspace" in detail else "resident",
                        reason="native-vulkan-allocation",
                    )
            suffix = f": {detail}" if detail else ""
            raise WeightBankError(f"{operation} failed (error {result}){suffix}")

    def _info(self, name: str) -> _TensorInfo:
        handle = self._require_open()
        info = _TensorInfo()
        self._check(self._tensor_info(handle, _as_c_string(name, "tensor name"), ctypes.byref(info)), "tensor_info")
        rank = int(info.rank)
        if rank < 1 or rank > 4:
            raise WeightBankError(f"tensor {name!r} has unsupported rank {rank}")
        dims = [int(info.dims[index]) for index in range(rank)]
        if any(dim <= 0 for dim in dims) or int(info.element_count) <= 0:
            raise WeightBankError(f"tensor {name!r} has invalid dimensions")
        if int(np.prod(np.asarray(dims, dtype=np.int64), dtype=np.int64)) != int(info.element_count):
            raise WeightBankError(f"tensor {name!r} has inconsistent dimensions")
        return info

    def tensor(self, name: str) -> np.ndarray:
        """Return one fully dequantized tensor in logical NumPy order.

        Native tensor dimensions are GGML ``ne[0..rank]`` (innermost first);
        NumPy consumers use the reversed shape.  Expert rank-3 tensors are
        rejected by the native ABI rather than silently materializing a whole
        expert bank.
        """
        if self._read_tensor_f32 is None:
            raise WeightBankError("native weight bank does not expose tensor reads")
        info = self._info(name)
        dims = tuple(int(info.dims[index]) for index in range(int(info.rank)))
        output = np.empty(int(info.element_count), dtype=np.float32)
        written = ctypes.c_size_t()
        self._check(
            self._read_tensor_f32(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(output.size),
                ctypes.byref(written),
            ),
            "tensor",
        )
        if int(written.value) != output.size:
            raise WeightBankError(
                f"tensor returned {int(written.value)} values for expected length {output.size}"
            )
        return output.reshape(tuple(reversed(dims)))


    def vector(self, name: str) -> np.ndarray:
        """Return one logical tensor vector as contiguous float32."""
        info = self._info(name)
        if int(info.rank) != 1:
            raise WeightBankError(f"vector requires rank-1 tensor {name!r}")
        length = int(info.element_count)
        output = np.empty(length, dtype=np.float32)
        written = ctypes.c_size_t()
        pointer = output.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self._check(
            self._read_vector(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                pointer,
                ctypes.c_size_t(length),
                ctypes.byref(written),
            ),
            "vector",
        )
        count = int(written.value)
        if count != length:
            raise WeightBankError(f"vector returned {count} values for expected length {length}")
        return output

    def embedding(self, name: str, token: int) -> np.ndarray:
        """Return one embedding row selected by token id."""
        info = self._info(name)
        if int(info.rank) != 2:
            raise WeightBankError(f"embedding requires rank-2 tensor {name!r}")
        if isinstance(token, bool) or not isinstance(token, (int, np.integer)) or int(token) < 0:
            raise WeightBankError("token must be a non-negative integer")
        # GGUF's logical orientation is [input, output].  Embedding rows are
        # selected by the native ABI along the output axis and have exactly
        # the inner width in dims[0]; do not infer this from min(dims), since
        # synthetic vocabularies may validly be smaller than hidden width.
        dims = [int(info.dims[0]), int(info.dims[1])]
        length = dims[0]
        output = np.empty(length, dtype=np.float32)
        written = ctypes.c_size_t()
        self._check(
            self._read_embedding(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                ctypes.c_uint64(int(token)),
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(length),
                ctypes.byref(written),
            ),
            "embedding",
        )
        count = int(written.value)
        if count <= 0 or count > length:
            raise WeightBankError(f"embedding returned invalid length {count}")
        return output[:count]

    def matvec(self, name: str, x: Any, expert: int | None = None) -> np.ndarray:
        """Multiply a GGUF matrix or projection vector by ``x``.

        A rank-1 tensor is a projection to width one, so it takes the same call
        path as a matrix and returns a single value.
        """
        info = self._info(name)
        if int(info.rank) < 1:
            raise WeightBankError(f"matvec requires rank >= 1 tensor {name!r}")
        vector = (
            x
            if isinstance(x, np.ndarray) and x.dtype == np.float32 and x.flags.c_contiguous
            else np.ascontiguousarray(x, dtype=np.float32)
        )
        if vector.ndim != 1:
            raise WeightBankError("matvec input must be one-dimensional")
        input_width = int(info.dims[0])
        output_width = int(info.dims[1])
        if vector.size != input_width:
            raise WeightBankError(f"matvec input has length {vector.size}, expected {input_width}")
        if not np.isfinite(vector).all():
            raise WeightBankError("matvec input contains a non-finite value")
        expert_value = -1 if expert is None else self._expert_id(expert)
        output = np.empty(output_width, dtype=np.float32)
        written = ctypes.c_size_t()
        self._check(
            self._matvec(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                vector.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(vector.size),
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(output.size),
                ctypes.byref(written),
                ctypes.c_int32(expert_value),
            ),
            "matvec",
        )
        count = int(written.value)
        if count != output_width:
            raise WeightBankError(f"matvec returned {count} values for expected length {output_width}")
        return output
    def matvec_batch(
        self, name: str, inputs: Any, expert: int | None = None
    ) -> np.ndarray:
        """Multiply one matrix by a row-major batch of independent vectors."""
        info = self._info(name)
        if int(info.rank) < 1:
            raise WeightBankError(f"matvec_batch requires rank >= 1 tensor {name!r}")
        try:
            matrix = (
                inputs
                if isinstance(inputs, np.ndarray)
                and inputs.dtype == np.float32
                and inputs.flags.c_contiguous
                else np.ascontiguousarray(inputs, dtype=np.float32)
            )
        except (TypeError, ValueError) as exc:
            raise WeightBankError("matvec_batch input must be numeric") from exc
        if matrix.ndim != 2 or matrix.shape[0] < 1:
            raise WeightBankError("matvec_batch input must be a non-empty two-dimensional array")
        input_width = int(info.dims[0])
        output_width = int(info.dims[1])
        if matrix.shape[1] != input_width:
            raise WeightBankError(
                f"matvec_batch input width is {matrix.shape[1]}, expected {input_width}"
            )
        if not np.isfinite(matrix).all():
            raise WeightBankError("matvec_batch input contains a non-finite value")
        # This is a real grouped native operation over distinct input rows.

        output = np.empty((matrix.shape[0], output_width), dtype=np.float32)
        written = ctypes.c_size_t()
        expert_value = -1 if expert is None else self._expert_id(expert)
        self._check(
            self._matvec_batch(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                matrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(matrix.shape[0]),
                ctypes.c_size_t(input_width),
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(output.size),
                ctypes.byref(written),
                ctypes.c_int32(expert_value),
            ),
            "matvec_batch",
        )
        if int(written.value) != output.size:
            raise WeightBankError(
                f"matvec_batch returned {written.value} values for expected length {output.size}"
            )
        return output

    def matvec_batch_experts(
        self, name: str, inputs: Any, experts: Any
    ) -> np.ndarray:
        """Multiply one tensor by a row-major batch whose rows name different
        expert slices of that tensor (``None`` selects a dense tensor).

        This is one native call: the bank partitions rows by expert internally
        so same-expert rows still share a single GGML plan.
        """
        if self._matvec_batch_experts is None:
            raise WeightBankError(
                "native weight bank does not expose matvec_batch_experts"
            )
        info = self._info(name)
        if int(info.rank) < 1:
            raise WeightBankError(
                f"matvec_batch_experts requires rank >= 1 tensor {name!r}"
            )
        try:
            matrix = (
                inputs
                if isinstance(inputs, np.ndarray)
                and inputs.dtype == np.float32
                and inputs.flags.c_contiguous
                else np.ascontiguousarray(inputs, dtype=np.float32)
            )
        except (TypeError, ValueError) as exc:
            raise WeightBankError("matvec_batch_experts input must be numeric") from exc
        if matrix.ndim != 2 or matrix.shape[0] < 1:
            raise WeightBankError(
                "matvec_batch_experts input must be a non-empty two-dimensional array"
            )
        input_width = int(info.dims[0])
        output_width = int(info.dims[1])
        if matrix.shape[1] != input_width:
            raise WeightBankError(
                f"matvec_batch_experts input width is {matrix.shape[1]}, expected {input_width}"
            )
        if not np.isfinite(matrix).all():
            raise WeightBankError(
                "matvec_batch_experts input contains a non-finite value"
            )
        try:
            expert_list = list(experts)
        except TypeError as exc:
            raise WeightBankError(
                "matvec_batch_experts experts must be a sequence"
            ) from exc
        if len(expert_list) != matrix.shape[0]:
            raise WeightBankError(
                f"matvec_batch_experts has {len(expert_list)} experts for "
                f"{matrix.shape[0]} input rows"
            )
        expert_values = np.empty(len(expert_list), dtype=np.int32)
        for index, expert in enumerate(expert_list):
            expert_values[index] = (
                -1 if expert is None else self._expert_id(expert)
            )
        output = np.empty((matrix.shape[0], output_width), dtype=np.float32)
        written = ctypes.c_size_t()
        self._check(
            self._matvec_batch_experts(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                matrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(matrix.shape[0]),
                ctypes.c_size_t(input_width),
                expert_values.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(output.size),
                ctypes.byref(written),
            ),
            "matvec_batch_experts",
        )
        if int(written.value) != output.size:
            raise WeightBankError(
                f"matvec_batch_experts returned {written.value} values for "
                f"expected length {output.size}"
            )
        return output


    @staticmethod
    def _expert_id(expert: int) -> int:
        if isinstance(expert, bool) or not isinstance(expert, (int, np.integer)) or int(expert) < 0:
            raise WeightBankError("expert must be a non-negative integer or None")
        value = int(expert)
        if value > 2_147_483_647:
            raise WeightBankError("expert exceeds native int32 range")
        return value

    def prefetch(self, name: str, expert: int | None = None) -> None:
        """Request native residency for one tensor/expert slice."""

        if self._prefetch is None:
            raise WeightBankError("native weight bank does not expose prefetch")
        expert_value = -1 if expert is None else self._expert_id(expert)
        self._check(
            self._prefetch(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                ctypes.c_int32(expert_value),
            ),
            "prefetch",
        )

    def matvec_many(self, requests: Any, x: Any) -> list[np.ndarray]:
        """Multiply several tensors by one shared contiguous input vector.

        Native implementations receive one input upload and one GGML graph;
        older libraries use the exact single-matvec path as a compatibility
        fallback.
        """
        if isinstance(requests, (str, bytes)):
            raise WeightBankError("matvec_many requests must be a sequence of pairs")
        try:
            request_list = list(requests)
        except TypeError as exc:
            raise WeightBankError("matvec_many requests must be a sequence of pairs") from exc
        if not request_list:
            raise WeightBankError("matvec_many requires at least one request")

        parsed: list[tuple[str, int | None, bytes, int]] = []
        for request in request_list:
            if not isinstance(request, (tuple, list)) or len(request) != 2:
                raise WeightBankError("each matvec_many request must be (tensor_name, expert)")
            name, expert = request
            encoded_name = _as_c_string(name, "tensor name")
            if expert is not None:
                expert_value = self._expert_id(expert)
            else:
                expert_value = -1
            parsed.append((name, expert, encoded_name, expert_value))
        try:
            vector = (
                x
                if isinstance(x, np.ndarray) and x.dtype == np.float32 and x.flags.c_contiguous
                else np.ascontiguousarray(x, dtype=np.float32)
            )
        except (TypeError, ValueError) as exc:
            raise WeightBankError("matvec_many input must be numeric") from exc
        if vector.ndim != 1:
            raise WeightBankError("matvec_many input must be one-dimensional")
        if not np.isfinite(vector).all():
            raise WeightBankError("matvec_many input contains a non-finite value")

        if self._matvec_many is None:
            return [
                self.matvec(name, vector, expert=expert)
                for name, expert, _encoded_name, _expert_value in parsed
            ]

        output_widths: list[int] = []
        for name, _expert, _encoded_name, _expert_value in parsed:
            info = self._info(name)
            if int(info.rank) < 1:
                raise WeightBankError(f"matvec requires rank >= 1 tensor {name!r}")
            input_width = int(info.dims[0])
            output_width = int(info.dims[1])
            if vector.size != input_width:
                raise WeightBankError(
                    f"matvec input has length {vector.size}, expected {input_width}"
                )
            output_widths.append(output_width)

        outputs = [np.empty(width, dtype=np.float32) for width in output_widths]
        names_array = (ctypes.c_char_p * len(parsed))(
            *(encoded_name for _name, _expert, encoded_name, _expert_value in parsed)
        )
        experts_array = (ctypes.c_int32 * len(parsed))(
            *(expert_value for _name, _expert, _encoded_name, expert_value in parsed)
        )
        output_ptrs = (ctypes.POINTER(ctypes.c_float) * len(outputs))(
            *(
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                for output in outputs
            )
        )
        capacities_array = (ctypes.c_size_t * len(outputs))(
            *(output.size for output in outputs)
        )
        counts_array = (ctypes.c_size_t * len(outputs))()
        self._check(
            self._matvec_many(
                self._require_open(),
                names_array,
                experts_array,
                ctypes.c_size_t(len(parsed)),
                vector.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                ctypes.c_size_t(vector.size),
                output_ptrs,
                capacities_array,
                counts_array,
            ),
            "matvec_many",
        )
        for index, (output, expected) in enumerate(zip(outputs, output_widths)):
            count = int(counts_array[index])
            if count != expected:
                raise WeightBankError(
                    f"matvec_many returned {count} values for expected length {expected}"
                )
            if not output.flags.c_contiguous or output.dtype != np.float32:
                raise WeightBankError("matvec_many returned a non-contiguous float32 output")
        return outputs
    


    def evict(self, name: str, expert: int | None = None) -> None:
        """Release native residency for one tensor/expert slice."""
        if self._evict is None:
            raise WeightBankError("native weight bank does not expose evict")
        expert_value = -1 if expert is None else self._expert_id(expert)
        self._check(
            self._evict(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                ctypes.c_int32(expert_value),
            ),
            "evict",
        )

    def residency(self, name: str, expert: int | None = None) -> dict[str, int | bool]:
        """Return native residency and hit/miss counters for one slice."""
        if self._residency is None:
            raise WeightBankError("native weight bank does not expose residency")
        expert_value = -1 if expert is None else self._expert_id(expert)
        resident = ctypes.c_int32()
        bytes_resident = ctypes.c_uint64()
        hits = ctypes.c_uint64()
        misses = ctypes.c_uint64()
        self._check(
            self._residency(
                self._require_open(),
                _as_c_string(name, "tensor name"),
                ctypes.c_int32(expert_value),
                ctypes.byref(resident),
                ctypes.byref(bytes_resident),
                ctypes.byref(hits),
                ctypes.byref(misses),
            ),
            "residency",
        )
        return {
            "resident": bool(resident.value),
            "bytes": int(bytes_resident.value),
            "hits": int(hits.value),
            "misses": int(misses.value),
        }

    def device_epoch(self, planes: np.ndarray, *, gain_ppm: int) -> "DeviceEpoch":
        """Open an uncommitted GPU field epoch on the weights' Vulkan device."""
        if self.backend not in {"vulkan", "vk"} or not self._device:
            raise WeightBankError("Vulkan neural epoch requires the native device ABI")
        return DeviceEpoch(self, planes, gain_ppm)

    def close(self) -> None:
        """Release the native context; safe to call more than once."""
        handle = self._handle
        if handle is None:
            return
        for epoch in tuple(self._device_epochs):
            epoch.close()
        self._handle = None
        try:
            if handle.value:
                self._close(handle)
        except Exception as exc:
            raise WeightBankError(f"weight bank close failed: {exc}") from exc

    def __enter__(self) -> "WeightBank":
        self._require_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown path
        try:
            self.close()
        except Exception:
            pass


class _DeviceTensor:
    __slots__ = ("epoch", "handle", "count")

    def __init__(self, epoch: "DeviceEpoch", handle: ctypes.c_void_p):
        self.epoch = epoch
        self.handle = handle
        size = ctypes.c_size_t()
        epoch._bank._check(
            epoch._bank._device["count"](epoch._handle, handle, ctypes.byref(size)),
            "device tensor count",
        )
        self.count = int(size.value)
        epoch._values.append(self)

    def close(self) -> None:
        handle, self.handle = self.handle, None
        if handle is not None and handle.value:
            self.epoch._bank._device["release"](handle)


class DeviceEpoch:
    """Candidate field planes and activations on one weight bank's Vulkan device."""

    def __init__(self, bank: WeightBank, planes: np.ndarray, gain_ppm: int):
        initial = np.ascontiguousarray(planes, dtype=np.float32)
        if initial.ndim != 2 or initial.shape[0] != 4 or initial.shape[1] == 0:
            raise ValueError("device field needs four nonempty plane-major F32 arrays")
        self._bank = bank
        self._mode_count = int(initial.shape[1])
        self._gain_ppm = int(gain_ppm)
        self._values: list[_DeviceTensor] = []
        self._sites: list[tuple[str, _DeviceTensor, _DeviceTensor, _DeviceTensor, _DeviceTensor]] = []
        handle = ctypes.c_void_p()
        bank._check(
            bank._device["epoch_begin"](
                bank._require_open(), initial.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                initial.size, self._mode_count, int(gain_ppm), ctypes.byref(handle),
            ),
            "Vulkan field epoch begin",
        )
        if not handle.value:
            raise WeightBankError("Vulkan field epoch begin returned no handle")
        self._handle: ctypes.c_void_p | None = handle
        bank._device_epochs.add(self)

    def _open(self) -> ctypes.c_void_p:
        if self._handle is None:
            raise WeightBankError("Vulkan field epoch is closed")
        return self._handle

    def fork_preview(self) -> "DeviceEpoch":
        """Copy the current Vulkan planes into a separate uncommitted epoch."""
        self._open()
        snapshot = self._bank._device.get("epoch_snapshot")
        if snapshot is None:
            raise WeightBankError(
                "Vulkan field epoch snapshots are unavailable in this native ABI"
            )
        planes = np.empty((4, self._mode_count), dtype=np.float32)
        count = ctypes.c_size_t()
        self._bank._check(
            snapshot(
                self._open(),
                planes.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                planes.size,
                ctypes.byref(count),
            ),
            "Vulkan field epoch snapshot",
        )
        if count.value != planes.size:
            raise WeightBankError("Vulkan field epoch snapshot returned incomplete planes")
        if not np.isfinite(planes).all():
            raise WeightBankError("Vulkan field epoch snapshot contains nonfinite values")
        return DeviceEpoch(self._bank, planes, self._gain_ppm)

    def _ptr(self, tensor: _DeviceTensor) -> ctypes.c_void_p:
        self._open()
        if not isinstance(tensor, _DeviceTensor) or tensor.epoch is not self or tensor.handle is None:
            raise WeightBankError("device tensor does not belong to this open epoch")
        return tensor.handle

    def _result(self, operation: str, function: Any, *arguments: Any) -> _DeviceTensor:
        output = ctypes.c_void_p()
        try:
            self._bank._check(function(*arguments, ctypes.byref(output)), operation)
            if not output.value:
                raise WeightBankError(f"{operation} returned no device tensor")
            return _DeviceTensor(self, output)
        except BaseException:
            if output.value:
                self._bank._device["release"](output)
            raise

    def upload(self, values: np.ndarray) -> _DeviceTensor:
        data = np.ascontiguousarray(np.asarray(values, dtype=np.float32).reshape(-1))
        return self._result(
            "device upload", self._bank._device["upload"], self._open(),
            data.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), data.size,
        )

    def view(self, input: _DeviceTensor, offset: int, count: int) -> _DeviceTensor:
        return self._result(
            "device view", self._bank._device["view"],
            self._open(), self._ptr(input), int(offset), int(count),
        )


    def low_rank_affine(
        self, input: _DeviceTensor, a: np.ndarray, b: np.ndarray, bias: np.ndarray,
        *, method_id: str,
    ) -> _DeviceTensor:
        """Evaluate ``(input @ a) @ b + bias`` entirely on this epoch's GPU.

        Coefficients use logical NumPy orientation ``a[input_width, rank]``,
        ``b[rank, output_width]``, and ``bias[output_width]``. Inputs may hold
        one or more consecutive rows whose flattened width is ``input_width``.
        ``method_id`` scopes immutable coefficient reuse to this epoch.
        """
        self._ptr(input)
        if not isinstance(method_id, str) or not method_id:
            raise ValueError("method_id must be non-empty text")
        a_array = np.ascontiguousarray(np.asarray(a, dtype=np.float32))
        b_array = np.ascontiguousarray(np.asarray(b, dtype=np.float32))
        bias_array = np.ascontiguousarray(np.asarray(bias, dtype=np.float32))
        if a_array.ndim != 2 or b_array.ndim != 2 or bias_array.ndim != 1:
            raise ValueError("low-rank affine expects A/B matrices and a bias vector")
        if a_array.shape[1] != b_array.shape[0] or b_array.shape[1] != bias_array.size:
            raise ValueError("low-rank affine coefficient dimensions do not match")
        if a_array.shape[0] <= 0 or a_array.shape[1] <= 0 or bias_array.size <= 0:
            raise ValueError("low-rank affine dimensions must be positive")
        if input.count % a_array.shape[0]:
            raise ValueError("input element count must contain complete input-width rows")
        if not (np.isfinite(a_array).all() and np.isfinite(b_array).all()
                and np.isfinite(bias_array).all()):
            raise ValueError("low-rank affine coefficients must be finite")
        return self._result(
            "device low-rank affine", self._bank._device["low_rank_affine"],
            self._open(), self._ptr(input), _as_c_string(method_id, "method_id"),
            a_array.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            a_array.shape[0], a_array.shape[1],
            b_array.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            b_array.shape[1],
            bias_array.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
    def matvec(self, name: str, input: _DeviceTensor, *, expert: int | None = None) -> _DeviceTensor:
        return self._result(
            "device matvec", self._bank._device["matvec"],
            self._open(), _as_c_string(name, "name"), self._ptr(input),
            -1 if expert is None else int(expert),
        )

    def matvec_many(
        self, names: tuple[str, ...], input: _DeviceTensor,
        *, experts: tuple[int | None, ...] | None = None,
    ) -> tuple[_DeviceTensor, ...]:
        if not names:
            return ()
        if experts is None:
            experts = (None,) * len(names)
        if len(experts) != len(names):
            raise ValueError("expert selection must match the matvec names")
        labels = (ctypes.c_char_p * len(names))(
            *(_as_c_string(name, "name") for name in names)
        )
        ids = (ctypes.c_int32 * len(names))(
            *(-1 if expert is None else int(expert) for expert in experts)
        )
        outputs = (ctypes.c_void_p * len(names))()
        created: list[_DeviceTensor] = []
        try:
            self._bank._check(
                self._bank._device["matvec_many"](
                    self._open(), labels, ids, len(names), self._ptr(input), outputs,
                ),
                "device matvec batch",
            )
            for ptr in outputs:
                created.append(_DeviceTensor(self, ctypes.c_void_p(ptr)))
            return tuple(created)
        except BaseException:
            for value in created:
                value.handle = None
            for ptr in outputs:
                if ptr:
                    self._bank._device["release"](ctypes.c_void_p(ptr))
            raise

    def exchange(self, site: str, input: _DeviceTensor) -> _DeviceTensor:
        capture, output, scale, delta = (
            ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        )
        pointers = (capture, output, scale, delta)
        created: list[_DeviceTensor] = []
        try:
            self._bank._check(
                self._bank._device["exchange"](
                    self._open(), _as_c_string(site, "site"), self._ptr(input),
                    *(ctypes.byref(ptr) for ptr in pointers),
                ),
                "device neural exchange",
            )
            for ptr in pointers:
                created.append(_DeviceTensor(self, ptr))
            self._sites.append((site, *created))
            return created[1]
        except BaseException:
            for value in created:
                value.handle = None
            for ptr in pointers:
                if ptr.value:
                    self._bank._device["release"](ptr)
            raise

    def _unary(self, operation: str, input: _DeviceTensor) -> _DeviceTensor:
        return self._result(
            f"device {operation}", self._bank._device[operation],
            self._open(), self._ptr(input),
        )

    def silu(self, input: _DeviceTensor) -> _DeviceTensor:
        return self._unary("silu", input)

    def sigmoid(self, input: _DeviceTensor) -> _DeviceTensor:
        return self._unary("sigmoid", input)

    def scale(self, input: _DeviceTensor, value: float) -> _DeviceTensor:
        return self._result(
            "device scale", self._bank._device["scale"],
            self._open(), self._ptr(input), ctypes.c_float(value),
        )

    def _binary(self, operation: str, left: _DeviceTensor, right: _DeviceTensor) -> _DeviceTensor:
        return self._result(
            f"device {operation}", self._bank._device[operation],
            self._open(), self._ptr(left), self._ptr(right),
        )

    def mul(self, left: _DeviceTensor, right: _DeviceTensor) -> _DeviceTensor:
        return self._binary("mul", left, right)

    def add(self, left: _DeviceTensor, right: _DeviceTensor) -> _DeviceTensor:
        return self._binary("add", left, right)

    def embedding(self, name: str, token: int) -> _DeviceTensor:
        if token < 0 or token >= 1 << 64:
            raise ValueError("embedding token is outside uint64 range")
        return self._result(
            "device embedding", self._bank._device["embedding"],
            self._open(), _as_c_string(name, "name"), token,
        )

    def concat(self, left: _DeviceTensor, right: _DeviceTensor) -> _DeviceTensor:
        return self._binary("concat", left, right)

    def norm_rows(
        self, input: _DeviceTensor, *, row_width: int, epsilon: float,
        sum_squares: bool, weight_name: str | None = None,
    ) -> _DeviceTensor:
        return self._result(
            "device row normalization", self._bank._device["norm_rows"],
            self._open(), self._ptr(input), row_width, ctypes.c_float(epsilon),
            int(sum_squares),
            None if weight_name is None else _as_c_string(weight_name, "weight name"),
        )

    def mul_rows(
        self, input: _DeviceTensor, row_scales: _DeviceTensor, *,
        row_width: int,
    ) -> _DeviceTensor:
        return self._result(
            "device row scaling", self._bank._device["mul_rows"],
            self._open(), self._ptr(input), self._ptr(row_scales), row_width,
        )

    def exp_clipped(
        self, input: _DeviceTensor, lower: float, upper: float,
    ) -> _DeviceTensor:
        return self._result(
            "device clipped exponential", self._bank._device["exp_clipped"],
            self._open(), self._ptr(input), ctypes.c_float(lower), ctypes.c_float(upper),
        )

    def softplus(self, input: _DeviceTensor) -> _DeviceTensor:
        return self._unary("softplus", input)

    def softmax(self, input: _DeviceTensor) -> _DeviceTensor:
        return self._unary("softmax", input)

    def positive_normalize(self, input: _DeviceTensor) -> _DeviceTensor:
        return self._unary("positive_normalize", input)

    def recurrent_conv(
        self, history: _DeviceTensor, kernel_name: str, *,
        channels: int,
    ) -> _DeviceTensor:
        return self._result(
            "device recurrent convolution", self._bank._device["recurrent_conv"],
            self._open(), self._ptr(history), _as_c_string(kernel_name, "kernel name"),
            channels,
        )

    def _recurrent(
        self, operation: str, state: _DeviceTensor, keys: _DeviceTensor,
        value_heads: int, key_heads: int, value_dim: int, key_dim: int,
        deltas: _DeviceTensor | None = None,
    ) -> _DeviceTensor:
        args: tuple[Any, ...] = (self._open(), self._ptr(state), self._ptr(keys))
        if deltas is not None:
            args += (self._ptr(deltas),)
        return self._result(
            f"device {operation}", self._bank._device[operation], *args,
            value_heads, key_heads, value_dim, key_dim,
        )

    def recurrent_predict(
        self, state: _DeviceTensor, keys: _DeviceTensor,
        value_heads: int, key_heads: int, value_dim: int, key_dim: int,
    ) -> _DeviceTensor:
        return self._recurrent(
            "recurrent_predict", state, keys, value_heads, key_heads, value_dim, key_dim,
        )

    def recurrent_update(
        self, state: _DeviceTensor, keys: _DeviceTensor, deltas: _DeviceTensor,
        value_heads: int, key_heads: int, value_dim: int, key_dim: int,
    ) -> _DeviceTensor:
        return self._recurrent(
            "recurrent_update", state, keys, value_heads, key_heads, value_dim, key_dim,
            deltas,
        )

    def recurrent_readout(
        self, state: _DeviceTensor, queries: _DeviceTensor,
        value_heads: int, key_heads: int, value_dim: int, key_dim: int,
    ) -> _DeviceTensor:
        return self._recurrent(
            "recurrent_readout", state, queries, value_heads, key_heads, value_dim, key_dim,
        )

    def rope(
        self, input: _DeviceTensor, position: int, sections: tuple[int, ...] | list[int],
        base: float,
    ) -> _DeviceTensor:
        sections_array = (ctypes.c_int32 * len(sections))(*sections)
        return self._result(
            "device RoPE", self._bank._device["rope"],
            self._open(), self._ptr(input), position, sections_array, len(sections),
            ctypes.c_double(base),
        )

    def attention_scores(
        self, query: _DeviceTensor, key_cache: _DeviceTensor,
        kv_head: int, kv_heads: int, head_dim: int, scale: float,
    ) -> _DeviceTensor:
        return self._result(
            "device attention scores", self._bank._device["attention_scores"],
            self._open(), self._ptr(query), self._ptr(key_cache),
            kv_head, kv_heads, head_dim, ctypes.c_float(scale),
        )

    def attention_context(
        self, probabilities: _DeviceTensor, value_cache: _DeviceTensor,
        kv_head: int, kv_heads: int, value_dim: int,
    ) -> _DeviceTensor:
        return self._result(
            "device attention context", self._bank._device["attention_context"],
            self._open(), self._ptr(probabilities), self._ptr(value_cache),
            kv_head, kv_heads, value_dim,
        )

    def download(self, input: _DeviceTensor) -> np.ndarray:
        result = np.empty(input.count, dtype=np.float32)
        count = ctypes.c_size_t()
        self._bank._check(
            self._bank._device["download"](
                self._open(), self._ptr(input),
                result.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                result.size, ctypes.byref(count),
            ),
            "device tensor download",
        )
        if count.value != input.count:
            raise WeightBankError("device tensor download returned an incomplete activation")
        if not np.isfinite(result).all():
            raise WeightBankError("device tensor download contains nonfinite values")
        return result

    def download_many(self, tensors: list[_DeviceTensor]) -> list[np.ndarray]:
        """Materialize ordered values in one contiguous GPU-to-host transfer."""
        if not tensors:
            return []
        capacity = sum(value.count for value in tensors)
        output = np.empty(capacity, dtype=np.float32)
        offsets = (ctypes.c_size_t * len(tensors))()
        counts = (ctypes.c_size_t * len(tensors))()
        transferred = ctypes.c_size_t()
        handles = (ctypes.c_void_p * len(tensors))(
            *(self._ptr(value) for value in tensors)
        )
        self._bank._check(
            self._bank._device["download_many"](
                self._open(), handles, len(tensors),
                output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                output.size, ctypes.byref(transferred), offsets, counts,
            ),
            "device packed download",
        )
        if transferred.value != capacity or any(
            counts[index] != value.count for index, value in enumerate(tensors)
        ):
            raise WeightBankError("device packed download returned incomplete values")
        if not np.isfinite(output).all():
            raise WeightBankError("device packed download contains nonfinite values")
        return [
            output[offsets[index]: offsets[index] + counts[index]]
            for index in range(len(tensors))
        ]

    def drain_sites(self) -> list[dict[str, Any]]:
        sites, self._sites = self._sites, []
        if not sites:
            return []
        values = self.download_many(
            [value for site in sites for value in site[1:]]
        )
        return [
            {"site": site, "input": values[4 * index],
             "output": values[4 * index + 1],
             "scale": float(values[4 * index + 2][0]),
             "delta": values[4 * index + 3]}
            for index, (site, *_captures) in enumerate(sites)
        ]

    def discard_stage_tensors(self) -> None:
        """Free activations after a committed stage; the four planes stay resident."""
        if self._sites:
            raise WeightBankError("device site captures must be recorded before stage release")
        values, self._values = self._values, []
        if values:
            handles = (ctypes.c_void_p * len(values))(
                *(value.handle.value if value.handle is not None else None for value in values)
            )
            for value in values:
                value.handle = None
            self._bank._device["release_many"](handles, len(values))

    def finish(self) -> np.ndarray:
        planes = np.empty((4, self._mode_count), dtype=np.float32)
        count = ctypes.c_size_t()
        self._bank._check(
            self._bank._device["epoch_finish"](
                self._open(), planes.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                planes.size, ctypes.byref(count),
            ),
            "Vulkan field epoch finish",
        )
        if count.value != planes.size:
            raise WeightBankError("Vulkan field epoch returned incomplete planes")
        if not np.isfinite(planes).all():
            raise WeightBankError("Vulkan field epoch contains nonfinite values")
        return planes

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        values, self._values = self._values, []
        self._sites.clear()
        if values:
            handles = (ctypes.c_void_p * len(values))(
                *(value.handle.value if value.handle is not None else None for value in values)
            )
            for value in values:
                value.handle = None
            self._bank._device["release_many"](handles, len(values))
        self._bank._device["epoch_close"](handle)

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown path
        if getattr(self, "_handle", None) is not None:
            self.close()


__all__ = ["WeightBank", "WeightBankError"]
