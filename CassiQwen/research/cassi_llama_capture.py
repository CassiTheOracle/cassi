#!/usr/bin/env python3
"""Read-only llama.cpp capture and graph-native intervention adapter.

The adapter speaks only to the pinned local C ABI.  It does not add adaptive
state: captured residuals, logits, and field states are copied into bounded
artifacts and returned as identity-bound evidence.  The field remains the
single adaptive object in the universal interpreter.
"""

from __future__ import annotations

import base64
import ctypes as ct
import hashlib
import json
import math
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_universal_interpreter import (
    ActivationTrace,
    ModelIdentity,
    OutputSnapshot,
    summarize_logits,
)


NATIVE_CAPTURE_SCHEMA = "cassi.universal-llm-native-capture.v2"
GRAPH_TRIAL_SCHEMA = "cassi.universal-llm-graph-trial.v2"

_LAYER_SET_BASENAME = "llama_set_embeddings_layer_inp"
_LAYER_GET_BASENAME = "llama_get_embeddings_layer_inp"
_MAX_CONTEXT = 4096
_MAX_TOKENS = 4096
_MAX_STATE_FLOATS = 4 * 9 * 6144
_MAX_LOGIT_DIFFERENCE = 1.0e-6
_CAPTURE_HEAD_INPUT = 0
_CAPTURE_ATTENTION_OUTPUT = 1
_CAPTURE_ATTENTION_PROBS = 2
_CAPTURE_EMBEDDING = 3
_CAPTURE_LAYER_INPUT = 4
_CAPTURE_FFN_INPUT = 5
_CAPTURE_FFN_OUTPUT = 6
_CAPTURE_HEAD_OUTPUT = 7
_CAPTURE_MAX_ELEMENTS = 16 * 1024 * 1024

_CAPTURE_SITE_KINDS = {
    "embedding": (_CAPTURE_EMBEDDING, None),
    "layer_input": (_CAPTURE_LAYER_INPUT, "layer"),
    "attention_output": (_CAPTURE_ATTENTION_OUTPUT, "layer"),
    "attention_probs": (_CAPTURE_ATTENTION_PROBS, "layer"),
    "ffn_input": (_CAPTURE_FFN_INPUT, "layer"),
    "ffn_output": (_CAPTURE_FFN_OUTPUT, "layer"),
    "head_input": (_CAPTURE_HEAD_INPUT, None),
    "head_output": (_CAPTURE_HEAD_OUTPUT, None),
}


class NativeCaptureError(RuntimeError):
    """Raised when a native capture or graph trial violates its contract."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NativeCaptureError(f"evidence is not canonical JSON: {error}") from error


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise NativeCaptureError(f"{name} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise NativeCaptureError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _f32_bytes(values: np.ndarray) -> bytes:
    array = np.ascontiguousarray(np.asarray(values, dtype="<f4"))
    return array.tobytes(order="C")


def _write_f32(path: Path, values: np.ndarray) -> dict[str, Any]:
    raw = _f32_bytes(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "path": path.name,
        "bytes": len(raw),
        "elements": int(np.asarray(values).size),
        "dtype": "float32",
        "endianness": "little",
        "order": "C",
        "sha256": _sha_bytes(raw),
    }


def _read_f32(path: Path, *, elements: int | None = None) -> np.ndarray:
    raw = Path(path).read_bytes()
    if len(raw) % 4:
        raise NativeCaptureError(f"{path} is not a complete float32 file")
    if elements is not None and len(raw) != elements * 4:
        raise NativeCaptureError(f"{path} has {len(raw) // 4} values, expected {elements}")
    values = np.frombuffer(raw, dtype="<f4").copy()
    if not bool(np.isfinite(values).all()):
        raise NativeCaptureError(f"{path} contains non-finite values")
    return values


def _raw_descriptor(path: Path, values: np.ndarray) -> dict[str, Any]:
    raw = _f32_bytes(values)
    return {
        "path": path.name,
        "bytes": len(raw),
        "elements": int(values.size),
        "dtype": "float32",
        "endianness": "little",
        "order": "C",
        "sha256": _sha_bytes(raw),
    }


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(_canonical(dict(value)) + b"\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class LlamaModelParams(ct.Structure):
    _fields_ = [
        ("devices", ct.c_void_p),
        ("tensor_buft_overrides", ct.c_void_p),
        ("n_gpu_layers", ct.c_int32),
        ("split_mode", ct.c_int32),
        ("load_mode", ct.c_int32),
        ("main_gpu", ct.c_int32),
        ("tensor_split", ct.c_void_p),
        ("progress_callback", ct.c_void_p),
        ("progress_callback_user_data", ct.c_void_p),
        ("kv_overrides", ct.c_void_p),
        ("vocab_only", ct.c_bool),
        ("check_tensors", ct.c_bool),
        ("use_extra_bufts", ct.c_bool),
        ("no_host", ct.c_bool),
        ("no_alloc", ct.c_bool),
        ("load_mtp", ct.c_bool),
    ]


class LlamaContextParams(ct.Structure):
    """The complete current context ABI, including Cassi extensions.

    This layout is copied from the active ``include/llama.h``.  The trailing
    fields matter because the context constructor receives this struct by
    value on Win64.
    """

    _fields_ = [
        ("n_ctx", ct.c_uint32),
        ("n_batch", ct.c_uint32),
        ("n_ubatch", ct.c_uint32),
        ("n_seq_max", ct.c_uint32),
        ("n_rs_seq", ct.c_uint32),
        ("n_outputs_max", ct.c_uint32),
        ("n_outputs_max_per_seq", ct.c_uint32),
        ("n_threads", ct.c_int32),
        ("n_threads_batch", ct.c_int32),
        ("ctx_type", ct.c_int32),
        ("rope_scaling_type", ct.c_int32),
        ("pooling_type", ct.c_int32),
        ("attention_type", ct.c_int32),
        ("flash_attn_type", ct.c_int32),
        ("rope_freq_base", ct.c_float),
        ("rope_freq_scale", ct.c_float),
        ("yarn_ext_factor", ct.c_float),
        ("yarn_attn_factor", ct.c_float),
        ("yarn_beta_fast", ct.c_float),
        ("yarn_beta_slow", ct.c_float),
        ("yarn_orig_ctx", ct.c_uint32),
        ("defrag_thold", ct.c_float),
        ("cb_eval", ct.c_void_p),
        ("cb_eval_user_data", ct.c_void_p),
        ("type_k", ct.c_int32),
        ("type_v", ct.c_int32),
        ("abort_callback", ct.c_void_p),
        ("abort_callback_data", ct.c_void_p),
        ("embeddings", ct.c_bool),
        ("offload_kqv", ct.c_bool),
        ("no_perf", ct.c_bool),
        ("op_offload", ct.c_bool),
        ("swa_full", ct.c_bool),
        ("kv_unified", ct.c_bool),
        ("cassi_modal", ct.c_bool),
        ("cassi_field_step", ct.c_bool),
        ("cassi_qi_field", ct.c_bool),
        ("cassi_apprentice", ct.c_bool),
        ("cassi_field_layer", ct.c_uint32),
        ("cassi_qi_field_layer", ct.c_uint32),
        ("cassi_qi_field_scales", ct.c_uint32),
        ("cassi_qi_field_wave_modes", ct.c_uint32),
        ("cassi_qi_field_fill_modes", ct.c_bool),
        ("cassi_qi_field_memory_fill", ct.c_bool),
        ("cassi_qi_field_row_width", ct.c_uint32),
        ("cassi_qi_displacement", ct.c_uint32),
        ("cassi_qi_intervention", ct.c_uint32),
        ("cassi_qi_field_steps", ct.c_uint32),
        ("cassi_qi_injection_scale", ct.c_float),
        ("cassi_qi_field_dt", ct.c_float),
        ("cassi_qi_substitute", ct.c_float),
        ("cassi_qi_energy_floor", ct.c_float),
        ("cassi_qi_read_floor", ct.c_float),
        ("cassi_qi_scale_read_taper", ct.c_float),
        ("cassi_qi_read_absolute", ct.c_bool),
        ("cassi_qi_modulate", ct.c_bool),
        ("cassi_qi_modulate_gain", ct.c_float),
        ("cassi_qi_attention_history", ct.c_bool),
        ("cassi_qi_unwritten_latch", ct.c_bool),
        ("cassi_attention_owned", ct.c_void_p),
        ("cassi_attention_owned_count", ct.c_uint32),
        ("samplers", ct.c_void_p),
        ("n_samplers", ct.c_size_t),
        ("ctx_other", ct.c_void_p),
        ("cassi_modal_retained_weight", ct.c_float),
        ("cassi_modal_phi", ct.c_float),
        ("cassi_modal_dt", ct.c_float),
        ("cassi_modal_omega2", ct.c_float),
        ("cassi_modal_coupling", ct.c_float),
        ("cassi_modal_steps_per_layer", ct.c_uint32),
    ]


class LlamaBatch(ct.Structure):
    _fields_ = [
        ("n_tokens", ct.c_int32),
        ("token", ct.POINTER(ct.c_int32)),
        ("embd", ct.POINTER(ct.c_float)),
        ("pos", ct.POINTER(ct.c_int32)),
        ("n_seq_id", ct.POINTER(ct.c_int32)),
        ("seq_id", ct.POINTER(ct.POINTER(ct.c_int32))),
        ("logits", ct.POINTER(ct.c_int8)),
    ]


if ct.sizeof(LlamaModelParams) != 72:
    raise RuntimeError(f"active llama model ABI must be 72 bytes, got {ct.sizeof(LlamaModelParams)}")
if ct.sizeof(LlamaContextParams) != 280:
    raise RuntimeError(f"active llama context ABI must be 280 bytes, got {ct.sizeof(LlamaContextParams)}")
if ct.sizeof(LlamaBatch) != 56:
    raise RuntimeError(f"active llama batch ABI must be 56 bytes, got {ct.sizeof(LlamaBatch)}")


@dataclass(slots=True)
class _BatchStorage:
    batch: LlamaBatch
    token_values: Any
    position_values: Any
    n_seq_values: Any
    sequence_values: Any
    sequence_pointers: Any
    logit_values: Any


def _build_batch(tokens: Sequence[int], *, position_start: int = 0) -> _BatchStorage:
    if not tokens or len(tokens) > _MAX_TOKENS:
        raise NativeCaptureError("token batch is empty or exceeds its fixed bound")
    if isinstance(position_start, bool) or not 0 <= int(position_start) <= _MAX_CONTEXT:
        raise NativeCaptureError("batch position start is outside its fixed bound")
    position_start = int(position_start)
    count = len(tokens)
    if position_start + count > _MAX_CONTEXT:
        raise NativeCaptureError("batch positions exceed the fixed context bound")
    token_values = (ct.c_int32 * count)(*map(int, tokens))
    position_values = (ct.c_int32 * count)(
        *(position_start + index for index in range(count))
    )
    n_seq_values = (ct.c_int32 * count)(*([1] * count))
    sequence_values = (ct.c_int32 * count)(*([0] * count))
    sequence_pointers = (ct.POINTER(ct.c_int32) * count)()
    for index in range(count):
        sequence_pointers[index] = ct.cast(
            ct.byref(sequence_values, index * ct.sizeof(ct.c_int32)),
            ct.POINTER(ct.c_int32),
        )
    logit_values = (ct.c_int8 * count)()
    logit_values[count - 1] = 1
    batch = LlamaBatch(
        n_tokens=count,
        token=token_values,
        embd=ct.POINTER(ct.c_float)(),
        pos=position_values,
        n_seq_id=n_seq_values,
        seq_id=sequence_pointers,
        logits=logit_values,
    )
    return _BatchStorage(
        batch=batch,
        token_values=token_values,
        position_values=position_values,
        n_seq_values=n_seq_values,
        sequence_values=sequence_values,
        sequence_pointers=sequence_pointers,
        logit_values=logit_values,
    )


def _pe_export_names(path: Path) -> list[str]:
    data = Path(path).read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise NativeCaptureError(f"{path.name} is not a PE image")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise NativeCaptureError(f"{path.name} has no PE signature")
    coff = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    magic = struct.unpack_from("<H", data, optional)[0]
    directory_offset = optional + (112 if magic == 0x20B else 96 if magic == 0x10B else -1)
    if directory_offset < 0:
        raise NativeCaptureError(f"{path.name} has unsupported PE header")
    export_rva, export_size = struct.unpack_from("<II", data, directory_offset)
    if not export_rva or not export_size:
        raise NativeCaptureError(f"{path.name} has no export directory")
    section_table = optional + optional_size
    sections: list[tuple[int, int, int]] = []
    for index in range(section_count):
        offset = section_table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, offset + 8)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_offset))

    def rva_to_offset(rva: int) -> int:
        for virtual_address, size, raw_offset in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_offset + rva - virtual_address
        raise NativeCaptureError(f"{path.name} export RVA is outside sections")

    export_offset = rva_to_offset(export_rva)
    number_of_names = struct.unpack_from("<I", data, export_offset + 24)[0]
    names_rva = struct.unpack_from("<I", data, export_offset + 32)[0]
    names_offset = rva_to_offset(names_rva)
    names: list[str] = []
    for index in range(number_of_names):
        name_rva = struct.unpack_from("<I", data, names_offset + index * 4)[0]
        name_offset = rva_to_offset(name_rva)
        end = data.find(b"\0", name_offset)
        if end < 0:
            raise NativeCaptureError(f"{path.name} contains an unterminated export name")
        names.append(data[name_offset:end].decode("ascii"))
    return names


def _resolve_hook_names(path: Path) -> dict[str, str]:
    names = _pe_export_names(path)
    resolved: dict[str, str] = {}
    for basename in (_LAYER_SET_BASENAME, _LAYER_GET_BASENAME):
        matches = [name for name in names if basename in name]
        if len(matches) != 1:
            raise NativeCaptureError(f"expected one export for {basename!r}, found {matches!r}")
        resolved[basename] = matches[0]
    return resolved


def _configure_public_api(lib: Any) -> None:
    lib.llama_version.argtypes = []
    lib.llama_version.restype = ct.c_char_p
    lib.llama_backend_init.argtypes = []
    lib.llama_backend_init.restype = None
    lib.llama_backend_free.argtypes = []
    lib.llama_backend_free.restype = None
    lib.llama_supports_gpu_offload.argtypes = []
    lib.llama_supports_gpu_offload.restype = ct.c_bool
    lib.llama_model_default_params.argtypes = []
    lib.llama_model_default_params.restype = LlamaModelParams
    lib.llama_context_default_params.argtypes = []
    lib.llama_context_default_params.restype = LlamaContextParams
    lib.llama_model_load_from_file.argtypes = [ct.c_char_p, LlamaModelParams]
    lib.llama_model_load_from_file.restype = ct.c_void_p
    lib.llama_model_free.argtypes = [ct.c_void_p]
    lib.llama_model_free.restype = None
    lib.llama_model_n_embd.argtypes = [ct.c_void_p]
    lib.llama_model_n_embd.restype = ct.c_int32
    lib.llama_model_n_layer.argtypes = [ct.c_void_p]
    lib.llama_model_n_layer.restype = ct.c_int32
    lib.llama_model_size.argtypes = [ct.c_void_p]
    lib.llama_model_size.restype = ct.c_size_t
    lib.llama_model_get_vocab.argtypes = [ct.c_void_p]
    lib.llama_model_get_vocab.restype = ct.c_void_p
    lib.llama_vocab_n_tokens.argtypes = [ct.c_void_p]
    lib.llama_vocab_n_tokens.restype = ct.c_int32
    lib.llama_tokenize.argtypes = [ct.c_void_p, ct.c_char_p, ct.c_int32, ct.POINTER(ct.c_int32), ct.c_int32, ct.c_bool, ct.c_bool]
    lib.llama_tokenize.restype = ct.c_int32
    lib.llama_init_from_model.argtypes = [ct.c_void_p, LlamaContextParams]
    lib.llama_init_from_model.restype = ct.c_void_p
    lib.llama_free.argtypes = [ct.c_void_p]
    lib.llama_free.restype = None
    lib.llama_decode.argtypes = [ct.c_void_p, LlamaBatch]
    lib.llama_decode.restype = ct.c_int32
    lib.llama_get_logits_ith.argtypes = [ct.c_void_p, ct.c_int32]
    lib.llama_get_logits_ith.restype = ct.POINTER(ct.c_float)
    lib.llama_cassi_qi_state_size.argtypes = [ct.c_void_p]
    lib.llama_cassi_qi_state_size.restype = ct.c_size_t
    lib.llama_cassi_qi_state_field_width.argtypes = [ct.c_void_p]
    lib.llama_cassi_qi_state_field_width.restype = ct.c_int64
    lib.llama_cassi_qi_state_row_width.argtypes = [ct.c_void_p]
    lib.llama_cassi_qi_state_row_width.restype = ct.c_int64
    lib.llama_cassi_qi_state_set.argtypes = [ct.c_void_p, ct.c_int32, ct.POINTER(ct.c_float), ct.c_size_t]
    lib.llama_cassi_qi_state_set.restype = ct.c_bool
    lib.llama_cassi_qi_mode_count.argtypes = [ct.c_void_p]
    lib.llama_cassi_qi_mode_count.restype = ct.c_size_t
    lib.llama_cassi_qi_mode_bank_set.argtypes = [ct.c_void_p, ct.POINTER(ct.c_float), ct.c_size_t]
    lib.llama_cassi_qi_mode_bank_set.restype = ct.c_bool
    lib.llama_cassi_qi_state_get.argtypes = [ct.c_void_p, ct.c_int32, ct.POINTER(ct.c_float), ct.c_size_t]
    lib.llama_cassi_capture_enable.argtypes = [ct.c_void_p]
    lib.llama_cassi_capture_enable.restype = ct.c_bool
    lib.llama_cassi_capture_shape.argtypes = [
        ct.c_void_p,
        ct.c_int32,
        ct.c_uint32,
        ct.POINTER(ct.c_int64),
    ]
    lib.llama_cassi_capture_shape.restype = ct.c_int32
    lib.llama_cassi_capture_copy.argtypes = [
        ct.c_void_p,
        ct.c_int32,
        ct.c_uint32,
        ct.POINTER(ct.c_float),
        ct.c_size_t,
    ]
    lib.llama_cassi_capture_copy.restype = ct.c_bool
    lib.llama_cassi_qi_graph_nodes.argtypes = [ct.c_void_p]
    lib.llama_cassi_qi_graph_nodes.restype = ct.c_int32


def _configure_hook_api(lib: Any, names: Mapping[str, str]) -> tuple[Any, Any]:
    setter = getattr(lib, names[_LAYER_SET_BASENAME])
    getter = getattr(lib, names[_LAYER_GET_BASENAME])
    setter.argtypes = [ct.c_void_p, ct.c_uint32, ct.c_bool]
    setter.restype = None
    getter.argtypes = [ct.c_void_p, ct.c_uint32]
    getter.restype = ct.POINTER(ct.c_float)
    return setter, getter


@dataclass(frozen=True, slots=True)
class NativeCapture:
    trace: ActivationTrace
    receipt: Mapping[str, Any]


class NativeLlamaSession:
    """One fresh model/backend session for capture or a graph trial."""

    def __init__(self, runtime_dir: Path | str, model_path: Path | str, *, gpu_layers: int = 99, context_tokens: int = 256, quantization: str = "declared-by-gguf") -> None:
        self.runtime_dir = Path(runtime_dir).resolve()
        self.model_path = Path(model_path).resolve()
        self.gpu_layers = int(gpu_layers)
        self.context_tokens = int(context_tokens)
        self.quantization = str(quantization)
        if not self.runtime_dir.is_dir():
            raise FileNotFoundError(self.runtime_dir)
        if not self.model_path.is_file():
            raise FileNotFoundError(self.model_path)
        if not 0 <= self.gpu_layers <= 512:
            raise NativeCaptureError("gpu_layers must be in [0, 512]")
        if not 1 <= self.context_tokens <= _MAX_CONTEXT:
            raise NativeCaptureError("context_tokens is outside its fixed bound")
        self.lib: Any = None
        self.model: Any = None
        self._cookie: Any = None
        self._handles: list[Any] = []
        self._backend_initialized = False
        self.hook_names: dict[str, str] = {}
        self.set_layer: Any = None
        self.get_layer: Any = None
        self.capture_enable: Any = None
        self.capture_shape: Any = None
        self.capture_copy: Any = None
        self.hidden_dimension = 0
        self.layer_count = 0
        self.vocabulary_size = 0
        self.runtime_files: list[dict[str, str]] = []

    def __enter__(self) -> "NativeLlamaSession":
        if os.name != "nt" or not hasattr(ct, "WinDLL"):
            raise NativeCaptureError("the llama ctypes adapter requires Windows WinDLL")
        llama_path = self.runtime_dir / "llama.dll"
        ggml_path = self.runtime_dir / "ggml.dll"
        ggml_base_path = self.runtime_dir / "ggml-base.dll"
        for path in (llama_path, ggml_path, ggml_base_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        self._cookie = os.add_dll_directory(str(self.runtime_dir))
        try:
            libomp = self.runtime_dir / "libomp140.x86_64.dll"
            if not libomp.is_file():
                for parent in self.runtime_dir.parents:
                    candidate = parent / "libomp140.x86_64.dll"
                    if candidate.is_file():
                        libomp = candidate
                        break
            load_paths = [libomp, ggml_base_path, ggml_path]
            ggml_handle: Any = None
            for path in load_paths:
                if path.is_file():
                    handle = ct.WinDLL(str(path))
                    self._handles.append(handle)
                    if path.resolve() == ggml_path.resolve():
                        ggml_handle = handle
            self._handles.append(ct.WinDLL(str(llama_path)))
            self.lib = self._handles[-1]
            if ggml_handle is None:
                raise NativeCaptureError("ggml.dll could not be loaded")
            _configure_public_api(self.lib)
            self.capture_enable = self.lib.llama_cassi_capture_enable
            self.capture_shape = self.lib.llama_cassi_capture_shape
            self.capture_copy = self.lib.llama_cassi_capture_copy
            self.hook_names = _resolve_hook_names(llama_path)
            self.set_layer, self.get_layer = _configure_hook_api(self.lib, self.hook_names)
            if not self.lib.llama_supports_gpu_offload():
                raise NativeCaptureError("runtime does not report GPU offload support")
            ggml_handle.ggml_backend_load_all_from_path.argtypes = [ct.c_char_p]
            ggml_handle.ggml_backend_load_all_from_path.restype = None
            ggml_handle.ggml_backend_load_all_from_path(os.fsencode(self.runtime_dir))
            version = (self.lib.llama_version() or b"").decode("utf-8")
            if not version:
                raise NativeCaptureError("llama_version returned an empty string")
            self.lib.llama_backend_init()
            self._backend_initialized = True
            model_params = self.lib.llama_model_default_params()
            model_params.n_gpu_layers = self.gpu_layers
            self.model = self.lib.llama_model_load_from_file(os.fsencode(self.model_path), model_params)
            if not self.model:
                raise NativeCaptureError("llama_model_load_from_file returned null")
            self.hidden_dimension = int(self.lib.llama_model_n_embd(self.model))
            self.layer_count = int(self.lib.llama_model_n_layer(self.model))
            vocab = self.lib.llama_model_get_vocab(self.model)
            self.vocabulary_size = int(self.lib.llama_vocab_n_tokens(vocab)) if vocab else 0
            if self.hidden_dimension <= 0 or self.layer_count <= 0 or self.vocabulary_size <= 0:
                raise NativeCaptureError("runtime returned invalid model dimensions")
            file_names = ("llama.dll", "ggml.dll", "ggml-base.dll", "ggml-cpu.dll", "ggml-vulkan.dll", "libomp140.x86_64.dll")
            for name in file_names:
                candidate = self.runtime_dir / name
                if not candidate.is_file():
                    for parent in self.runtime_dir.parents:
                        alternate = parent / name
                        if alternate.is_file():
                            candidate = alternate
                            break
                if candidate.is_file():
                    self.runtime_files.append({"name": name, "sha256": _sha_path(candidate)})
            return self
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.model:
            self.lib.llama_model_free(self.model)
            self.model = None
        if self._backend_initialized and self.lib is not None:
            self.lib.llama_backend_free()
            self._backend_initialized = False
        self._handles.clear()
        if self._cookie is not None:
            self._cookie.close()
            self._cookie = None

    def __enter_subclass__(self) -> "NativeLlamaSession":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()

    @property
    def model_identity(self) -> ModelIdentity:
        if self.model is None:
            raise NativeCaptureError("model session is not open")
        model_sha = _sha_path(self.model_path)
        runtime_sha = _sha_bytes(_canonical(sorted(self.runtime_files, key=lambda row: row["name"])))
        tokenizer_sha = _sha_bytes(f"embedded-gguf-tokenizer:{model_sha}".encode("ascii"))
        backend = "vulkan" if self.gpu_layers > 0 else "cpu"
        return ModelIdentity(
            model_id=self.model_path.name,
            model_sha256=model_sha,
            architecture="qwen35",
            quantization=self.quantization,
            tokenizer_sha256=tokenizer_sha,
            runtime_id=f"llama.cpp:{(self.lib.llama_version() or b'').decode('utf-8')}",
            runtime_sha256=runtime_sha,
            context_tokens=self.context_tokens,
            embedding_width=self.hidden_dimension,
            layer_count=self.layer_count,
            backend=backend,
            hook_sites=(
                "embedding",
                "layer_input",
                "attention_output",
                "attention_probs",
                "ffn_input",
                "ffn_output",
                "head_input",
                "head_output",
            ),
        )

    def _tokenize(
        self,
        prompt: str,
        *,
        add_bos: bool = True,
        add_special: bool = True,
    ) -> list[int]:
        if not isinstance(prompt, str) or not prompt:
            raise NativeCaptureError("prompt must be a nonempty string")
        raw = prompt.encode("utf-8")
        capacity = max(32, len(raw) + 8)
        vocab = self.lib.llama_model_get_vocab(self.model)
        buffer = (ct.c_int32 * capacity)()
        count = int(self.lib.llama_tokenize(vocab, raw, len(raw), buffer, capacity, add_bos, add_special))
        if count < 0:
            capacity = -count
            buffer = (ct.c_int32 * capacity)()
            count = int(self.lib.llama_tokenize(vocab, raw, len(raw), buffer, capacity, add_bos, add_special))
        if count <= 0 or count > self.context_tokens:
            raise NativeCaptureError(f"prompt token count {count} is outside context {self.context_tokens}")
        return [int(buffer[index]) for index in range(count)]

    def tokenize_text(self, text: str) -> list[int]:
        """Tokenize a probe label without BOS/EOS decoration."""

        return self._tokenize(text, add_bos=False, add_special=False)

    def _params(self, *, layer: int, displacement: int, injection_scale: float, substitute: float, field_enabled: bool, read_absolute: bool = False, unwritten_latch: bool = False, scale_read_taper: float = 0.0, row_width: int = 0, fill_modes: bool = False, memory_fill: bool = False) -> LlamaContextParams:
        if not 0 <= layer < self.layer_count:
            raise NativeCaptureError(f"field layer {layer} is outside the model")
        if displacement not in {0, 3, 4, 5, 6}:
            raise NativeCaptureError("displacement must be one of 0, 3, 4, 5, 6")
        if not math.isfinite(float(injection_scale)) or float(injection_scale) < 0.0:
            raise NativeCaptureError("injection_scale must be finite and nonnegative")
        if not math.isfinite(float(substitute)) or not 0.0 <= float(substitute) <= 1.0:
            raise NativeCaptureError("substitute must be in [0, 1]")
        params = self.lib.llama_context_default_params()
        params.flash_attn_type = 0
        params.n_ctx = self.context_tokens
        params.n_batch = self.context_tokens
        params.n_ubatch = min(self.context_tokens, 128)
        params.n_seq_max = 1
        params.n_rs_seq = 0
        params.n_outputs_max = self.context_tokens
        params.n_outputs_max_per_seq = self.context_tokens
        params.cassi_modal = False
        params.cassi_field_step = False
        params.cassi_qi_field = bool(field_enabled)
        params.cassi_apprentice = False
        params.cassi_field_layer = layer
        params.cassi_qi_field_layer = layer
        params.cassi_qi_field_scales = 4
        params.cassi_qi_field_wave_modes = 0
        params.cassi_qi_field_fill_modes = bool(fill_modes)
        params.cassi_qi_field_memory_fill = bool(memory_fill)
        params.cassi_qi_field_row_width = int(row_width)
        params.cassi_qi_displacement = displacement
        params.cassi_qi_intervention = 0
        params.cassi_qi_field_steps = 1
        params.cassi_qi_injection_scale = float(injection_scale)
        params.cassi_qi_field_dt = 0.005
        params.cassi_qi_substitute = float(substitute)
        params.cassi_qi_energy_floor = 1.0e-6
        params.cassi_qi_read_floor = 0.05
        params.cassi_qi_read_absolute = bool(read_absolute)
        params.cassi_qi_scale_read_taper = float(scale_read_taper)
        params.cassi_qi_modulate = False
        params.cassi_qi_modulate_gain = 0.0
        params.cassi_qi_attention_history = False
        params.cassi_qi_unwritten_latch = bool(unwritten_latch)
        params.cassi_attention_owned = None
        params.cassi_attention_owned_count = 0
        params.samplers = None
        params.n_samplers = 0
        params.ctx_other = None
        params.cassi_modal_retained_weight = 0.9
        params.cassi_modal_phi = 1.618033988749895
        params.cassi_modal_dt = 0.005
        params.cassi_modal_omega2 = 20.0
        params.cassi_modal_coupling = 1.0
        params.cassi_modal_steps_per_layer = 4
        return params

    def _decode_logits(
        self,
        context: Any,
        tokens: Sequence[int],
        *,
        position_start: int = 0,
    ) -> np.ndarray:
        batch = _build_batch(tokens, position_start=position_start)
        status = int(self.lib.llama_decode(context, batch.batch))
        if status != 0:
            raise NativeCaptureError(f"llama_decode returned {status}")
        pointer = self.lib.llama_get_logits_ith(context, -1)
        if not pointer:
            raise NativeCaptureError("llama_get_logits_ith returned null")
        values = np.ctypeslib.as_array(pointer, shape=(self.vocabulary_size,)).astype(np.float32, copy=True)
        if not bool(np.isfinite(values).all()):
            raise NativeCaptureError("native logits contain non-finite values")
        return values

    def probe_logits(self, prompt: str) -> tuple[list[int], np.ndarray]:
        """Read one native next-token distribution without field or hooks."""

        tokens = self._tokenize(prompt)
        params = self._params(
            layer=self.layer_count - 1,
            displacement=0,
            injection_scale=0.0,
            substitute=0.0,
            field_enabled=False,
        )
        context = self._new_context(params)
        try:
            logits = self._decode_logits(context, tokens)
        finally:
            self.lib.llama_free(context)
        return tokens, logits

    def _new_context(self, params: LlamaContextParams) -> Any:
        context = self.lib.llama_init_from_model(self.model, params)
        if not context:
            raise NativeCaptureError("llama_init_from_model returned null")
        return context

    def _load_mode_bank(self, context: Any, source: Path | str) -> dict[str, Any]:
        """Install a learned per-mode damping bank on a live field context."""

        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        mode_count = int(self.lib.llama_cassi_qi_mode_count(context))
        if mode_count <= 0:
            raise NativeCaptureError("native Qi mode count is unavailable for a bank")
        bank = _read_f32(path, elements=mode_count)
        pointer = bank.ctypes.data_as(ct.POINTER(ct.c_float))
        if not self.lib.llama_cassi_qi_mode_bank_set(context, pointer, mode_count):
            raise NativeCaptureError("native Qi mode bank installation failed")
        return {
            "path": path.name,
            "sha256": _sha_path(path),
            "bytes": path.stat().st_size,
            "modes": mode_count,
            "damping_min": float(bank.min()),
            "damping_max": float(bank.max()),
        }

    def _copy_capture_tensor(
        self,
        context: Any,
        *,
        kind: int,
        layer: int,
    ) -> tuple[tuple[int, ...], np.ndarray] | None:
        shape_buffer = (ct.c_int64 * 4)()
        rank = int(self.capture_shape(context, int(kind), int(layer), shape_buffer))
        if rank == 0:
            return None
        if not 1 <= rank <= 4:
            raise NativeCaptureError(f"capture kind {kind} returned invalid rank {rank}")
        shape = tuple(int(shape_buffer[index]) for index in range(rank))
        if any(value <= 0 for value in shape):
            raise NativeCaptureError(f"capture kind {kind} returned invalid shape {shape}")
        elements = math.prod(shape)
        if elements > _CAPTURE_MAX_ELEMENTS:
            raise NativeCaptureError(f"capture kind {kind} exceeds its fixed size bound")
        values = np.empty(elements, dtype=np.float32)
        pointer = values.ctypes.data_as(ct.POINTER(ct.c_float))
        if not self.capture_copy(context, int(kind), int(layer), pointer, elements):
            raise NativeCaptureError(f"capture kind {kind} layer {layer} could not be copied")
        if not bool(np.isfinite(values).all()):
            raise NativeCaptureError(f"capture kind {kind} layer {layer} contains non-finite values")
        return shape, values

    def capture(
        self,
        *,
        prompt: str,
        sequence_id: str,
        adapter_key: str | None = None,
        native_role: str | None = None,
        layer: int | None = None,
        output_dir: Path | str,
    ) -> NativeCapture:
        """Capture a native trace and optionally bind its declared task role."""
        layer_index = self.layer_count // 2 if layer is None else int(layer)
        if not 0 <= layer_index < self.layer_count:
            raise NativeCaptureError(f"capture layer {layer_index} is outside the model")
        tokens = self._tokenize(prompt)
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        model_identity = self.model_identity
        off_context = self._new_context(self._params(layer=layer_index, displacement=0, injection_scale=0.0, substitute=0.0, field_enabled=False))
        try:
            logits_off = self._decode_logits(off_context, tokens)
        finally:
            self.lib.llama_free(off_context)

        on_context = self._new_context(self._params(layer=layer_index, displacement=0, injection_scale=0.0, substitute=0.0, field_enabled=False))
        capture_sites: dict[str, list[dict[str, Any]]] = {}
        capture_values: dict[tuple[str, int | None], np.ndarray] = {}
        try:
            self.set_layer(on_context, layer_index, True)
            if not self.capture_enable(on_context):
                raise NativeCaptureError("native graph capture could not be enabled")
            logits_on = self._decode_logits(on_context, tokens)
            for site_name, (kind, layer_mode) in _CAPTURE_SITE_KINDS.items():
                rows: list[dict[str, Any]] = []
                requested_layers = range(self.layer_count) if layer_mode is not None else (None,)
                for capture_layer in requested_layers:
                    layer_argument = 0 if capture_layer is None else int(capture_layer)
                    copied = self._copy_capture_tensor(
                        on_context,
                        kind=kind,
                        layer=layer_argument,
                    )
                    if copied is None:
                        if site_name == "attention_probs":
                            continue
                        raise NativeCaptureError(
                            f"required capture site {site_name} layer {capture_layer} is absent"
                        )
                    shape, values = copied
                    if capture_layer is None:
                        filename = f"{site_name}.f32"
                    elif site_name == "layer_input" and capture_layer == layer_index:
                        filename = "layer-input.f32"
                    else:
                        filename = f"{site_name}-layer-{capture_layer}.f32"
                    descriptor = _write_f32(output_dir / filename, values)
                    descriptor.update(
                        {
                            "kind": int(kind),
                            "site": site_name,
                            "layer": capture_layer,
                            "rank": len(shape),
                            "shape": list(shape),
                        }
                    )
                    rows.append(descriptor)
                    capture_values[(site_name, capture_layer)] = values
                if not rows and site_name != "attention_probs":
                    raise NativeCaptureError(f"required capture site {site_name} returned no tensors")
                capture_sites[site_name] = rows

            hidden_values = capture_values[("layer_input", layer_index)]
            expected_elements = self.hidden_dimension * len(tokens)
            if hidden_values.size != expected_elements:
                raise NativeCaptureError(
                    f"layer capture has {hidden_values.size} values, expected {expected_elements}"
                )
            offset = (len(tokens) - 1) * self.hidden_dimension
            hidden = hidden_values[offset : offset + self.hidden_dimension].copy()
            legacy_pointer = self.get_layer(on_context, layer_index)
            if not legacy_pointer:
                raise NativeCaptureError("legacy layer capture getter returned null")
            legacy_address = ct.addressof(legacy_pointer.contents) + offset * ct.sizeof(ct.c_float)
            legacy_hidden = np.ctypeslib.as_array(
                ct.cast(legacy_address, ct.POINTER(ct.c_float)),
                shape=(self.hidden_dimension,),
            ).astype(np.float32, copy=True)
            if not np.array_equal(hidden, legacy_hidden):
                raise NativeCaptureError("graph layer capture differs from the legacy layer hook")
            head_output = capture_values[("head_output", None)]
            if head_output.size != logits_on.size or not np.array_equal(head_output, logits_on):
                raise NativeCaptureError("graph head output differs from the public logits readout")
        finally:
            self.set_layer(on_context, layer_index, False)
            self.lib.llama_free(on_context)

        max_difference = float(np.max(np.abs(logits_on.astype(np.float64) - logits_off.astype(np.float64))))
        off_readout = summarize_logits(logits_off)
        on_readout = summarize_logits(logits_on)
        parity = {
            "argmax_match": off_readout.top_token_id == on_readout.top_token_id,
            "top16_token_ids_match": np.argsort(logits_off)[::-1][:16].tolist() == np.argsort(logits_on)[::-1][:16].tolist(),
            "max_abs_logit_difference": max_difference,
            "max_abs_logit_difference_bound": _MAX_LOGIT_DIFFERENCE,
            "pass": max_difference <= _MAX_LOGIT_DIFFERENCE and off_readout.top_token_id == on_readout.top_token_id,
        }
        if not parity["pass"]:
            raise NativeCaptureError(f"capture parity failed: {parity}")

        off_file = output_dir / "logits-off.f32"
        on_file = output_dir / "logits-on.f32"
        hidden_file = output_dir / "layer-input-final.f32"
        off_descriptor = _write_f32(off_file, logits_off)
        on_descriptor = _write_f32(on_file, logits_on)
        hidden_descriptor = _write_f32(hidden_file, hidden)
        hidden_descriptor.update(
            {
                "kind": _CAPTURE_LAYER_INPUT,
                "site": "layer_input",
                "layer": layer_index,
                "rank": 1,
                "shape": [self.hidden_dimension],
            }
        )
        prompt_bytes = prompt.encode("utf-8")
        trace = ActivationTrace(
            model=model_identity,
            site="layer_input",
            layer=layer_index,
            sequence_id=sequence_id,
            position=len(tokens) - 1,
            values=hidden,
            token_id=tokens[-1],
            logits=logits_on,
            adapter_key=adapter_key,
            prompt_sha256=_sha_bytes(prompt_bytes),
            capture_sha256=hidden_descriptor["sha256"],
            source_id=str(hidden_file),
        )
        if native_role is not None:
            trace = trace.with_role_attestation(native_role)
        capture_summary = {
            name: {
                "requested_layers": self.layer_count if layer_mode is not None else 1,
                "available_layers": len(capture_sites[name]),
                "layers": sorted(
                    int(row["layer"])
                    for row in capture_sites[name]
                    if row["layer"] is not None
                ),
                "optional": name == "attention_probs",
                "shapes": sorted({tuple(int(extent) for extent in row["shape"]) for row in capture_sites[name]}),
                "sha256": sorted(str(row["sha256"]) for row in capture_sites[name]),
            }
            for name, (_kind, layer_mode) in _CAPTURE_SITE_KINDS.items()
        }
        capture_summary = {
            name: {
                **summary,
                "shapes": [list(shape) for shape in summary["shapes"]],
            }
            for name, summary in capture_summary.items()
        }
        receipt: dict[str, Any] = {
            "schema": NATIVE_CAPTURE_SCHEMA,
            "model": model_identity.as_dict(),
            "model_fingerprint": model_identity.fingerprint,
            "runtime": {
                "directory": self.runtime_dir.name,
                "version": (self.lib.llama_version() or b"").decode("utf-8"),
                "files": sorted(self.runtime_files, key=lambda row: row["name"]),
                "gpu_layers": self.gpu_layers,
                "context_tokens": self.context_tokens,
            },
            "hook": {
                "kind": "graph_capture_bundle",
                "site": "layer_input",
                "layer_index": layer_index,
                "token_row": len(tokens) - 1,
                "setter_export": self.hook_names[_LAYER_SET_BASENAME],
                "getter_export": self.hook_names[_LAYER_GET_BASENAME],
                "enable_export": "llama_cassi_capture_enable",
                "shape_export": "llama_cassi_capture_shape",
                "copy_export": "llama_cassi_capture_copy",
            },
            "capture_contract": {
                "selector_abi": {
                    name: int(kind)
                    for name, (kind, _layer_mode) in _CAPTURE_SITE_KINDS.items()
                },
                "layer_count": self.layer_count,
                "attention_probabilities_optional": True,
                "shape_slots": 4,
            },
            "capture_sites": capture_sites,
            "capture_summary": capture_summary,
            "prompt": {
                "utf8": prompt,
                "sha256": _sha_bytes(prompt_bytes),
                "token_ids": tokens,
                "token_count": len(tokens),
                "final_token_index": len(tokens) - 1,
                "final_token_id": tokens[-1],
            },
            "capture_off": {**off_descriptor, "readout": off_readout.as_dict()},
            "capture_on": {**on_descriptor, "readout": on_readout.as_dict()},
            "hidden_state": hidden_descriptor,
            "trace": trace.as_dict(),
            "parity": parity,
            "verdict": "PASS",
        }
        _atomic_json(output_dir / "capture-receipt.json", receipt)
        return NativeCapture(trace=trace, receipt=receipt)

    def graph_trial(
        self,
        *,
        prompt: str,
        sequence_id: str,
        state_path: Path | str,
        output_dir: Path | str,
        displacement: int,
        injection_scale: float = 0.0,
        substitute: float = 0.0,
        layer: int | None = None,
        capture_id: str = "graph-trial",
        continuation_tokens: Sequence[int] = (),
        read_absolute: bool = False,
        unwritten_latch: bool = False,
        scale_read_taper: float = 0.0,
        mode_bank: Path | str | None = None,
        row_width: int = 0,
        fill_modes: bool = False,
        memory_fill: bool = False,
    ) -> dict[str, Any]:
        layer_index = self.layer_count // 2 if layer is None else int(layer)
        source_state = Path(state_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        model_identity = self.model_identity
        tokens = self._tokenize(prompt)
        try:
            continuation = tuple(int(token) for token in continuation_tokens)
        except (TypeError, ValueError, OverflowError) as error:
            raise NativeCaptureError("continuation_tokens must contain token ids") from error
        if len(tokens) + len(continuation) > self.context_tokens:
            raise NativeCaptureError("prompt and continuation exceed the fixed context")
        if any(token < 0 or token >= self.vocabulary_size for token in continuation):
            raise NativeCaptureError("continuation token is outside the model vocabulary")
        context = self._new_context(self._params(
            layer=layer_index,
            displacement=displacement,
            injection_scale=injection_scale,
            substitute=substitute,
            field_enabled=True,
            read_absolute=read_absolute,
            unwritten_latch=unwritten_latch,
            scale_read_taper=scale_read_taper,
            row_width=row_width,
            fill_modes=fill_modes,
            memory_fill=memory_fill,
        ))
        try:
            bank_descriptor = None if mode_bank is None else self._load_mode_bank(context, mode_bank)
            state_size = int(self.lib.llama_cassi_qi_state_size(context))
            state = _read_f32(source_state, elements=state_size)
            if state_size <= 0 or state_size > _MAX_STATE_FLOATS:
                raise NativeCaptureError(f"native Qi state size {state_size} is outside its bound")
            state_pointer = state.ctypes.data_as(ct.POINTER(ct.c_float))
            if not self.lib.llama_cassi_qi_state_set(context, 0, state_pointer, state_size):
                raise NativeCaptureError("native Qi state installation failed")
            step_values: list[tuple[int, int, np.ndarray]] = []
            logits = self._decode_logits(context, tokens)
            step_values.append((len(tokens) - 1, tokens[-1], logits))
            for step, token in enumerate(continuation):
                logits = self._decode_logits(
                    context,
                    (token,),
                    position_start=len(tokens) + step,
                )
                step_values.append((len(tokens) + step, token, logits))
            final_state = np.zeros(state_size, dtype=np.float32)
            final_pointer = final_state.ctypes.data_as(ct.POINTER(ct.c_float))
            if not self.lib.llama_cassi_qi_state_get(context, 0, final_pointer, state_size):
                raise NativeCaptureError("native Qi state retrieval failed")
            graph_nodes = int(self.lib.llama_cassi_qi_graph_nodes(context))
            model_size = int(self.lib.llama_model_size(self.model))
            field_width = int(self.lib.llama_cassi_qi_state_field_width(context))
            row_width = int(self.lib.llama_cassi_qi_state_row_width(context))
        finally:
            self.lib.llama_free(context)
        if field_width < 0 or row_width < 0 or field_width > row_width:
            raise NativeCaptureError(
                f"native Qi ownership widths are invalid: field={field_width}, row={row_width}"
            )
        logits_steps: list[dict[str, Any]] = []
        for step, (position, input_token_id, values) in enumerate(step_values):
            filename = "logits.f32" if step == len(step_values) - 1 else f"logits-step-{step}.f32"
            descriptor = _write_f32(output_dir / filename, values)
            descriptor.update({
                "step": step,
                "position": position,
                "input_token_id": int(input_token_id),
                "top_token_id": int(np.argmax(values)),
            })
            logits_steps.append(descriptor)
        logits_descriptor = logits_steps[-1]
        state_descriptor = _write_f32(output_dir / "state-after.f32", final_state)
        output_owner = "field" if displacement >= 6 else "model"
        decode_steps = len(logits_steps)
        output_position = int(logits_steps[-1]["position"])
        snapshot = OutputSnapshot(
            model=model_identity,
            site="layer_input",
            layer=layer_index,
            sequence_id=sequence_id,
            position=output_position,
            prompt_sha256=_sha_bytes(prompt.encode("utf-8")),
            logits=logits,
            route="graph-native",
            executed=True,
            capture_id=capture_id,
        )
        state_write_owner = (
            "field"
            if field_width > 0
            else "suppressed-model"
            if displacement >= 3
            else "model"
        )
        receipt: dict[str, Any] = {
            "schema": GRAPH_TRIAL_SCHEMA,
            "verdict": "PASS",
            "model": model_identity.as_dict(),
            "model_fingerprint": model_identity.fingerprint,
            "configuration": {
                "prompt_sha256": _sha_bytes(prompt.encode("utf-8")),
                "prompt_tokens": len(tokens),
                "continuation_tokens": list(continuation),
                "decode_steps": decode_steps,
                "output_position": output_position,
                "sequence_id": sequence_id,
                "site": "layer_input",
                "layer": layer_index,
                "displacement": displacement,
                "injection_scale": float(injection_scale),
                "substitute": float(substitute),
                "field_scales": 4,
                "field_enabled": True,
                "read_absolute": bool(read_absolute),
                "unwritten_latch": bool(unwritten_latch),
                "scale_read_taper": float(scale_read_taper),
                "mode_bank": bank_descriptor,
                "row_width": int(row_width),
                "fill_modes": bool(fill_modes),
                "memory_fill": bool(memory_fill),
            },
            "state_predecessor": {
                "path": os.path.relpath(source_state, output_dir).replace("\\", "/"),
                "sha256": _sha_path(source_state),
                "bytes": source_state.stat().st_size,
                "elements": state_size,
            },
            "state_successor": state_descriptor,
            "logit_steps": logits_steps,
            "logits": logits_descriptor,
            "graph": {
                "executed": True,
                "nodes": graph_nodes,
                "decode_steps": decode_steps,
                "qwen_forward_passes": decode_steps,
                "model_logits_read": (0 if displacement >= 6 else 1) * decode_steps,
                "field_logits_read": (1 if displacement >= 6 else 0) * decode_steps,
                "lm_head_rows_computed": (0 if displacement >= 6 else 1) * decode_steps,
                "lm_head_rows_skipped": (1 if displacement >= 6 else 0) * decode_steps,
                "sampler_steps": 0,
                "qwen_tensor_bytes_loaded": model_size,
                "output_owner": output_owner,
                "lm_head_owner": output_owner,
                "logit_owner": output_owner,
                "sampler_owner": "none",
                "qi_state_field_width": field_width,
                "qi_state_row_width": row_width,
                "qi_state_field_bytes": field_width * 4,
                "qi_state_remaining_model_bytes": (row_width - field_width) * 4,
                "qi_state_write_owner": state_write_owner,
                "qi_state_tail_owner": "model" if 0 < field_width < row_width else "none",
            },
            "output_snapshot": snapshot.as_dict(),
        }
        _atomic_json(output_dir / "graph-trial-receipt.json", receipt)
        return {"snapshot": snapshot, "receipt": receipt}


def load_capture_receipt(path: Path | str) -> NativeCapture:
    """Reconstruct an immutable trace from a capture receipt and raw files."""

    receipt_path = Path(path).resolve()
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    if value.get("schema") != NATIVE_CAPTURE_SCHEMA or value.get("verdict") != "PASS":
        raise NativeCaptureError("capture receipt schema or verdict is invalid")
    model_data = value.get("model")
    if not isinstance(model_data, Mapping):
        raise NativeCaptureError("capture receipt omits model identity")
    model_fields = {key: item for key, item in model_data.items() if key != "schema"}
    model = ModelIdentity(**model_fields)
    prompt = value.get("prompt")
    hook = value.get("hook")
    trace_data = value.get("trace")
    if not isinstance(prompt, Mapping) or not isinstance(hook, Mapping) or not isinstance(trace_data, Mapping):
        raise NativeCaptureError("capture receipt is missing prompt, hook, or trace")
    directory = receipt_path.parent
    on_descriptor = value.get("capture_on")
    hidden_descriptor = value.get("hidden_state")
    if not isinstance(on_descriptor, Mapping) or not isinstance(hidden_descriptor, Mapping):
        raise NativeCaptureError("capture receipt omits raw capture descriptors")
    logits_path = directory / str(on_descriptor["path"])
    hidden_path = directory / str(hidden_descriptor["path"])
    logits = _read_f32(logits_path, elements=int(on_descriptor["elements"]))
    hidden = _read_f32(hidden_path, elements=int(hidden_descriptor["elements"]))
    if _sha_path(logits_path) != on_descriptor.get("sha256") or _sha_path(hidden_path) != hidden_descriptor.get("sha256"):
        raise NativeCaptureError("capture raw-file digest mismatch")
    trace = ActivationTrace(
        model=model,
        site=str(trace_data.get("site", "layer_input")),
        layer=int(trace_data["layer"]),
        sequence_id=str(trace_data["sequence_id"]),
        position=int(trace_data["position"]),
        values=hidden,
        token_id=trace_data.get("token_id"),
        expected_token_id=trace_data.get("expected_token_id"),
        logits=logits,
        adapter_key=trace_data.get("adapter_key"),
        prompt_sha256=prompt.get("sha256"),
        capture_sha256=hidden_descriptor.get("sha256"),
        source_id=str(hidden_path),
        native_role=trace_data.get("native_role"),
        role_attestation=trace_data.get("role_attestation"),
    )
    if trace.trace_sha256 != trace_data.get("trace_sha256"):
        raise NativeCaptureError("reconstructed trace digest differs from receipt")
    return NativeCapture(trace=trace, receipt=value)


def load_graph_trial(path: Path | str) -> dict[str, Any]:
    """Load and independently validate a graph trial's linked logits/state."""

    receipt_path = Path(path).resolve()
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    if value.get("schema") != GRAPH_TRIAL_SCHEMA or value.get("verdict") != "PASS":
        raise NativeCaptureError("graph trial receipt schema or verdict is invalid")
    directory = receipt_path.parent
    configuration = value.get("configuration")
    graph = value.get("graph")
    if not isinstance(configuration, Mapping) or not isinstance(graph, Mapping):
        raise NativeCaptureError("graph trial omits configuration or graph")
    continuation = configuration.get("continuation_tokens")
    steps = value.get("logit_steps")
    if not isinstance(continuation, list) or not isinstance(steps, list) or not steps:
        raise NativeCaptureError("graph trial omits its continuation step ledger")
    expected_steps = 1 + len(continuation)
    if int(configuration.get("decode_steps", -1)) != expected_steps:
        raise NativeCaptureError("graph trial continuation step count is inconsistent")
    if int(graph.get("decode_steps", -1)) != expected_steps or int(graph.get("qwen_forward_passes", -1)) != expected_steps:
        raise NativeCaptureError("graph trial native forward count is inconsistent")
    final_values: np.ndarray | None = None
    for step, descriptor in enumerate(steps):
        if not isinstance(descriptor, Mapping):
            raise NativeCaptureError("graph trial step descriptor is malformed")
        if int(descriptor.get("step", -1)) != step:
            raise NativeCaptureError("graph trial step index is not contiguous")
        expected_position = int(configuration["prompt_tokens"]) - 1 + step
        if int(descriptor.get("position", -1)) != expected_position:
            raise NativeCaptureError("graph trial step position is inconsistent")
        linked = (directory / str(descriptor["path"])).resolve()
        try:
            linked.relative_to(directory.resolve())
        except ValueError as error:
            raise NativeCaptureError("graph trial step escapes its receipt directory") from error
        values = _read_f32(linked, elements=int(descriptor["elements"]))
        if _sha_path(linked) != descriptor.get("sha256"):
            raise NativeCaptureError(f"graph trial step digest mismatch: {linked.name}")
        if int(np.argmax(values)) != int(descriptor.get("top_token_id")):
            raise NativeCaptureError("graph trial step top token does not match raw logits")
        if step == len(steps) - 1:
            final_values = values
    descriptor = value.get("logits")
    if not isinstance(descriptor, Mapping) or final_values is None:
        raise NativeCaptureError("graph trial omits final logits")
    linked = (directory / str(descriptor["path"])).resolve()
    logits = _read_f32(linked, elements=int(descriptor["elements"]))
    if _sha_path(linked) != descriptor.get("sha256") or not np.array_equal(logits, final_values):
        raise NativeCaptureError("graph trial final logits do not match its step ledger")
    state_descriptor = value.get("state_successor")
    if not isinstance(state_descriptor, Mapping):
        raise NativeCaptureError("graph trial omits state_successor")
    state_path = (directory / str(state_descriptor["path"])).resolve()
    _read_f32(state_path, elements=int(state_descriptor["elements"]))
    if _sha_path(state_path) != state_descriptor.get("sha256"):
        raise NativeCaptureError("graph trial state successor digest mismatch")
    field_width = int(graph.get("qi_state_field_width", -1))
    row_width = int(graph.get("qi_state_row_width", -1))
    if field_width < 0 or row_width < 0 or field_width > row_width:
        raise NativeCaptureError("graph trial Qi ownership widths are invalid")
    if int(graph.get("qi_state_field_bytes", -1)) != field_width * 4:
        raise NativeCaptureError("graph trial field ownership bytes are inconsistent")
    if int(graph.get("qi_state_remaining_model_bytes", -1)) != (row_width - field_width) * 4:
        raise NativeCaptureError("graph trial remaining ownership bytes are inconsistent")
    return value


def write_zero_state(path: Path | str, *, elements: int = 4 * 9 * 6144) -> Path:
    if not 1 <= int(elements) <= _MAX_STATE_FLOATS:
        raise NativeCaptureError("zero-state size is outside its fixed bound")
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_f32(destination, np.zeros(int(elements), dtype=np.float32))
    return destination


def causal_pair_from_trials(
    baseline: Mapping[str, Any],
    lesion: Mapping[str, Any],
    *,
    intervention_kind: str,
    donor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Rehydrate snapshots from trial receipts and run the shared assessor."""

    def snapshot(trial: Mapping[str, Any]) -> OutputSnapshot:
        model_data = trial.get("model")
        config = trial.get("configuration")
        descriptor = trial.get("logits")
        if not isinstance(model_data, Mapping) or not isinstance(config, Mapping) or not isinstance(descriptor, Mapping):
            raise NativeCaptureError("graph trial is missing snapshot identity")
        model = ModelIdentity(**{key: item for key, item in model_data.items() if key != "schema"})
        logits_path = Path(trial.get("_receipt_path", ""))
        if not logits_path:
            raise NativeCaptureError("graph trial path is required for snapshot rehydration")
        logits = _read_f32(logits_path.parent / str(descriptor["path"]), elements=int(descriptor["elements"]))
        continuation = config.get("continuation_tokens", [])
        if not isinstance(continuation, list):
            raise NativeCaptureError("graph trial continuation ledger is malformed")
        output_position = int(config.get(
            "output_position",
            int(config["prompt_tokens"]) - 1 + len(continuation),
        ))
        return OutputSnapshot(
            model=model,
            site=str(config["site"]),
            layer=int(config["layer"]),
            sequence_id=str(config["sequence_id"]),
            position=output_position,
            prompt_sha256=str(config["prompt_sha256"]),
            logits=logits,
            route="graph-native",
            executed=True,
            capture_id=str(trial.get("output_snapshot", {}).get("capture_id", "graph-trial")),
        )

    from cassi_universal_interpreter import CausalPair

    pair = CausalPair(
        baseline=snapshot(baseline),
        lesion=snapshot(lesion),
        donor=None if donor is None else snapshot(donor),
        intervention_kind=intervention_kind,
    )
    return pair.assess()


__all__ = [
    "GRAPH_TRIAL_SCHEMA",
    "NATIVE_CAPTURE_SCHEMA",
    "LlamaBatch",
    "LlamaContextParams",
    "LlamaModelParams",
    "NativeCapture",
    "NativeCaptureError",
    "NativeLlamaSession",
    "causal_pair_from_trials",
    "load_capture_receipt",
    "load_graph_trial",
    "write_zero_state",
]
