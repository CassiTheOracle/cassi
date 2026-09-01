"""Read one Qwen residual state from the installed llama.cpp b10472 DLL.

This is a lab-only ctypes bridge for the frozen L16 protocol.  It never starts
llama-server, opens a socket, writes model/KV state, or supplies an activation
back to llama.cpp.  The two layer-input functions are WIP C++ APIs in pinned
llama.cpp `src/llama-ext.h`; they are deliberately resolved from the live PE
export table rather than declared as stable public C APIs.

ABI source: ggml-org/llama.cpp commit 60eeeb608:
- include/llama.h: model/context params, batch, decode, logits, tokenizer;
- src/llama-ext.h: layer-input function signatures;
- src/llama-context.cpp: final capture row is token-indexed in the layer buffer.
"""

from __future__ import annotations

import argparse
import base64
import ctypes as ct
import hashlib
import json
import math
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from cassi_fi_paths import ARTIFACT_DIR, QWEN_DLL_DIR, QWEN_MODEL_PATH


PROTOCOL = "CassiQwen L16 hidden-state field observatory"
VERSION = 1
EXPECTED_LLAMA_VERSION = "0.1.1-dev"
EXPECTED_MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
EXPECTED_HIDDEN_DIMENSION = 5120
CONTEXT_SIZE = 512
TOP_K = 16
MAX_LOGIT_DIFFERENCE = 1.0e-6
PROMPT = b"Cassi hidden-state observatory: reply with exactly one physical field name."
LAYER_SET_BASENAME = "llama_set_embeddings_layer_inp"
LAYER_GET_BASENAME = "llama_get_embeddings_layer_inp"
LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x00000100


# Exact natural Win64 layouts from b10472 include/llama.h.  Never use
# `_pack_`: the ABI uses ordinary C/C++ alignment.  These sizes are checked
# before calling default-param functions returned by value.
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
        ("samplers", ct.c_void_p),
        ("n_samplers", ct.c_size_t),
        ("ctx_other", ct.c_void_p),
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
    raise RuntimeError(f"b10472 model params ABI is 72 bytes, got {ct.sizeof(LlamaModelParams)}")
if ct.sizeof(LlamaContextParams) != 160:
    raise RuntimeError(f"b10472 context params ABI is 160 bytes, got {ct.sizeof(LlamaContextParams)}")
if ct.sizeof(LlamaBatch) != 56:
    raise RuntimeError(f"b10472 batch ABI is 56 bytes, got {ct.sizeof(LlamaBatch)}")


class ProbeError(RuntimeError):
    """A checked L16 contract failure."""


@dataclass
class BatchStorage:
    batch: LlamaBatch
    token_values: Any
    position_values: Any
    n_seq_values: Any
    sequence_values: Any
    sequence_pointers: Any
    logit_values: Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def float32_bytes(values: np.ndarray) -> bytes:
    array = np.asarray(values, dtype="<f4")
    if not array.flags.c_contiguous:
        array = np.ascontiguousarray(array)
    return array.tobytes(order="C")


def float32_base64(values: np.ndarray) -> str:
    return base64.b64encode(float32_bytes(values)).decode("ascii")


def assert_finite(values: np.ndarray, label: str) -> None:
    if not np.isfinite(values).all():
        raise ProbeError(f"{label} contains non-finite values")


def top_k(logits: np.ndarray, count: int = TOP_K) -> list[dict[str, float | int]]:
    if logits.ndim != 1 or logits.size < count:
        raise ProbeError(f"logits cannot supply top-{count}")
    token_ids = np.arange(logits.size, dtype=np.int64)
    # Deterministic token-id tie-break, then descending float32 logit.
    order = np.lexsort((token_ids, -logits.astype(np.float64, copy=False)))[:count]
    return [{"token_id": int(index), "logit": float(logits[index])} for index in order]


def pe_export_names(path: Path) -> list[str]:
    """Return named PE exports without requiring dumpbin or an import library."""
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ProbeError(f"{path.name} is not an MZ PE image")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ProbeError(f"{path.name} has no PE signature")
    coff = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic == 0x20B:
        data_directory = optional + 112
    elif magic == 0x10B:
        data_directory = optional + 96
    else:
        raise ProbeError(f"{path.name} has unsupported PE optional-header magic {magic:#x}")
    export_rva, export_size = struct.unpack_from("<II", data, data_directory)
    if export_rva == 0 or export_size == 0:
        raise ProbeError(f"{path.name} has no export directory")
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
        raise ProbeError(f"{path.name} export RVA {rva:#x} is outside sections")

    export_offset = rva_to_offset(export_rva)
    number_of_names = struct.unpack_from("<I", data, export_offset + 24)[0]
    names_rva = struct.unpack_from("<I", data, export_offset + 32)[0]
    names_offset = rva_to_offset(names_rva)
    names: list[str] = []
    for index in range(number_of_names):
        name_rva = struct.unpack_from("<I", data, names_offset + index * 4)[0]
        name_offset = rva_to_offset(name_rva)
        terminator = data.find(b"\0", name_offset)
        if terminator < 0:
            raise ProbeError(f"{path.name} has unterminated export name")
        names.append(data[name_offset:terminator].decode("ascii"))
    return names


def resolve_wip_hook_names(dll_path: Path) -> dict[str, str]:
    names = pe_export_names(dll_path)
    resolved: dict[str, str] = {}
    for basename in (LAYER_SET_BASENAME, LAYER_GET_BASENAME):
        matches = [name for name in names if basename in name]
        if len(matches) != 1:
            raise ProbeError(f"expected one DLL export containing {basename!r}, found {matches!r}")
        resolved[basename] = matches[0]
    return resolved


def configure_public_api(lib: ct.WinDLL) -> None:
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


def configure_wip_hooks(lib: ct.WinDLL, names: dict[str, str]) -> tuple[Callable[..., None], Callable[..., Any]]:
    setter = getattr(lib, names[LAYER_SET_BASENAME])
    getter = getattr(lib, names[LAYER_GET_BASENAME])
    setter.argtypes = [ct.c_void_p, ct.c_uint32, ct.c_bool]
    setter.restype = None
    getter.argtypes = [ct.c_void_p, ct.c_uint32]
    getter.restype = ct.POINTER(ct.c_float)
    return setter, getter


def tokenize(lib: ct.WinDLL, vocab: int, prompt: bytes) -> list[int]:
    capacity = max(32, len(prompt) + 8)
    token_buffer = (ct.c_int32 * capacity)()
    count = int(lib.llama_tokenize(vocab, prompt, len(prompt), token_buffer, capacity, True, True))
    if count < 0:
        capacity = -count
        token_buffer = (ct.c_int32 * capacity)()
        count = int(lib.llama_tokenize(vocab, prompt, len(prompt), token_buffer, capacity, True, True))
    if count <= 0:
        raise ProbeError(f"tokenization failed with result {count}")
    return [int(token_buffer[index]) for index in range(count)]


def build_batch(tokens: list[int]) -> BatchStorage:
    if not tokens:
        raise ProbeError("cannot build an empty prompt batch")
    count = len(tokens)
    token_values = (ct.c_int32 * count)(*tokens)
    position_values = (ct.c_int32 * count)(*range(count))
    n_seq_values = (ct.c_int32 * count)(*([1] * count))
    sequence_values = (ct.c_int32 * count)(*([0] * count))
    sequence_pointers = (ct.POINTER(ct.c_int32) * count)()
    for index in range(count):
        sequence_pointers[index] = ct.cast(
            ct.byref(sequence_values, index * ct.sizeof(ct.c_int32)), ct.POINTER(ct.c_int32)
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
    return BatchStorage(batch, token_values, position_values, n_seq_values, sequence_values, sequence_pointers, logit_values)


def make_context(lib: ct.WinDLL, model: int, context_size: int) -> int:
    params = lib.llama_context_default_params()
    params.n_ctx = context_size
    params.n_batch = context_size
    params.n_ubatch = context_size
    params.n_seq_max = 1
    context = int(lib.llama_init_from_model(model, params) or 0)
    if context == 0:
        raise ProbeError("llama_init_from_model returned null")
    return context


def run_prompt(
    lib: ct.WinDLL,
    model: int,
    batch_storage: BatchStorage,
    vocabulary_size: int,
    hidden_dimension: int,
    layer_index: int,
    context_size: int,
    set_layer: Callable[..., None] | None = None,
    get_layer: Callable[..., Any] | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    context = make_context(lib, model, context_size)
    enabled = False
    try:
        if set_layer is not None:
            if get_layer is None:
                raise ProbeError("layer capture getter is absent")
            set_layer(context, layer_index, True)
            enabled = True
        status = int(lib.llama_decode(context, batch_storage.batch))
        if status != 0:
            raise ProbeError(f"llama_decode returned {status}")
        logits_pointer = lib.llama_get_logits_ith(context, -1)
        if not logits_pointer:
            raise ProbeError("llama_get_logits_ith returned null")
        logits = np.ctypeslib.as_array(logits_pointer, shape=(vocabulary_size,)).astype(np.float32, copy=True)
        assert_finite(logits, "logits")
        hidden: np.ndarray | None = None
        if enabled:
            layer_pointer = get_layer(context, layer_index)
            if not layer_pointer:
                raise ProbeError("llama_get_embeddings_layer_inp returned null")
            final_offset = (batch_storage.batch.n_tokens - 1) * hidden_dimension
            raw_address = ct.addressof(layer_pointer.contents) + final_offset * ct.sizeof(ct.c_float)
            final_pointer = ct.cast(raw_address, ct.POINTER(ct.c_float))
            hidden = np.ctypeslib.as_array(final_pointer, shape=(hidden_dimension,)).astype(np.float32, copy=True)
            assert_finite(hidden, "captured hidden state")
            if not float(np.linalg.norm(hidden.astype(np.float64))) > 0.0:
                raise ProbeError("captured hidden state has zero L2 norm")
        return logits, hidden
    finally:
        if enabled:
            # Keeps the local context internally consistent even though it is
            # immediately freed; this never injects or changes an activation.
            set_layer(context, layer_index, False)
        lib.llama_free(context)


def capture_receipt(args: argparse.Namespace) -> dict[str, Any]:
    runtime_dir = args.dll_dir.resolve()
    model_path = args.model.resolve()
    llama_path = runtime_dir / "llama.dll"
    ggml_path = runtime_dir / "ggml.dll"
    ggml_base_path = runtime_dir / "ggml-base.dll"
    omp_path = runtime_dir / "libomp140.x86_64.dll"
    for path in (model_path, llama_path, ggml_path, ggml_base_path, omp_path):
        if not path.is_file():
            raise ProbeError(f"required local artifact is missing: {path}")
    if args.context_size != CONTEXT_SIZE:
        raise ProbeError(f"L16 freezes context_size={CONTEXT_SIZE}, got {args.context_size}")
    if args.gpu_layers != 99:
        raise ProbeError("L16 freezes gpu_layers=99")

    model_hash = sha256_file(model_path)
    if model_hash != EXPECTED_MODEL_SHA256:
        raise ProbeError(f"GGUF SHA-256 mismatch: {model_hash}")
    hook_names = resolve_wip_hook_names(llama_path)

    # The cookie must live through all DLL loads; no global PATH mutation.
    directory_cookie = os.add_dll_directory(str(runtime_dir))
    backend_initialized = False
    model = 0
    try:
        # b10472's ggml-base.dll imports libomp, and ggml.dll imports the
        # base DLL. Load this sibling chain explicitly before asking ggml to
        # discover the local Vulkan backend plugins.
        ct.WinDLL(str(omp_path))
        ct.WinDLL(str(ggml_base_path))
        ggml = ct.WinDLL(str(ggml_path))
        ggml.ggml_backend_load_all_from_path.argtypes = [ct.c_char_p]
        ggml.ggml_backend_load_all_from_path.restype = None
        ggml.ggml_backend_load_all_from_path(os.fsencode(runtime_dir))

        lib = ct.WinDLL(str(llama_path))
        configure_public_api(lib)
        set_layer, get_layer = configure_wip_hooks(lib, hook_names)
        version = (lib.llama_version() or b"").decode("utf-8")
        if version != EXPECTED_LLAMA_VERSION:
            raise ProbeError(f"llama_version mismatch: {version!r}")
        if not bool(lib.llama_supports_gpu_offload()):
            raise ProbeError("installed llama runtime does not report GPU offload support")
        lib.llama_backend_init()
        backend_initialized = True

        model_params = lib.llama_model_default_params()
        model_params.n_gpu_layers = args.gpu_layers
        model = int(lib.llama_model_load_from_file(os.fsencode(model_path), model_params) or 0)
        if model == 0:
            raise ProbeError("llama_model_load_from_file returned null")
        hidden_dimension = int(lib.llama_model_n_embd(model))
        layer_count = int(lib.llama_model_n_layer(model))
        if hidden_dimension != EXPECTED_HIDDEN_DIMENSION:
            raise ProbeError(f"model hidden width mismatch: {hidden_dimension}")
        if layer_count <= 0:
            raise ProbeError(f"model layer count is invalid: {layer_count}")
        layer_index = layer_count // 2
        if layer_index < 0 or layer_index >= layer_count:
            raise ProbeError(f"selected layer index {layer_index} is invalid for {layer_count} layers")

        vocabulary = int(lib.llama_model_get_vocab(model) or 0)
        if vocabulary == 0:
            raise ProbeError("llama_model_get_vocab returned null")
        vocabulary_size = int(lib.llama_vocab_n_tokens(vocabulary))
        if vocabulary_size <= 0:
            raise ProbeError(f"model vocabulary size is invalid: {vocabulary_size}")
        token_ids = tokenize(lib, vocabulary, PROMPT)
        if len(token_ids) > args.context_size:
            raise ProbeError(f"prompt has {len(token_ids)} tokens, exceeds context {args.context_size}")
        batch_storage = build_batch(token_ids)

        logits_off, _ = run_prompt(
            lib, model, batch_storage, vocabulary_size, hidden_dimension, layer_index, args.context_size
        )
        logits_on, hidden = run_prompt(
            lib,
            model,
            batch_storage,
            vocabulary_size,
            hidden_dimension,
            layer_index,
            args.context_size,
            set_layer,
            get_layer,
        )
        if hidden is None:
            raise ProbeError("capture-on execution returned no hidden state")
        assert_finite(hidden, "captured hidden state")
        hidden_norm = float(np.linalg.norm(hidden.astype(np.float64)))
        if not math.isfinite(hidden_norm) or hidden_norm <= 0.0:
            raise ProbeError("captured hidden L2 norm is not finite and positive")

        max_difference = float(np.max(np.abs(logits_on.astype(np.float64) - logits_off.astype(np.float64))))
        off_top = top_k(logits_off)
        on_top = top_k(logits_on)
        argmax_off = int(np.argmax(logits_off))
        argmax_on = int(np.argmax(logits_on))
        top_ids_match = [row["token_id"] for row in off_top] == [row["token_id"] for row in on_top]
        parity_pass = argmax_off == argmax_on and top_ids_match and max_difference <= MAX_LOGIT_DIFFERENCE

        hidden_raw = float32_bytes(hidden)
        logits_off_raw = float32_bytes(logits_off)
        logits_on_raw = float32_bytes(logits_on)
        return {
            "protocol": PROTOCOL,
            "version": VERSION,
            "model": {
                "path": model_path.name,
                "sha256": model_hash,
                "architecture": "qwen35",
                "hidden_dimension": hidden_dimension,
                "layer_count": layer_count,
                "vocabulary_size": vocabulary_size,
            },
            "runtime": {
                "llama_dll": llama_path.name,
                "llama_dll_sha256": sha256_file(llama_path),
                "ggml_dll": ggml_path.name,
                "ggml_dll_sha256": sha256_file(ggml_path),
                "llama_version": version,
                "package_build": 10472,
                "ggml_base_dll": ggml_base_path.name,
                "ggml_base_dll_sha256": sha256_file(ggml_base_path),
                "package_commit": "60eeeb608",
                "openmp_dll": omp_path.name,
                "openmp_dll_sha256": sha256_file(omp_path),
                "backend_loader": "ggml_backend_load_all_from_path",
                "backend_path": runtime_dir.name,
                "requested_gpu_layers": args.gpu_layers,
                "context_size": args.context_size,
                "batch_size": args.context_size,
            },
            "hook": {
                "kind": "layer_input_residual",
                "layer_rule": "floor(n_layer / 2)",
                "layer_index": layer_index,
                "token_row": len(token_ids) - 1,
                "setter_export": hook_names[LAYER_SET_BASENAME],
                "getter_export": hook_names[LAYER_GET_BASENAME],
                "source": "llama.cpp 60eeeb608 src/llama-ext.h",
            },
            "prompt": {
                "utf8": PROMPT.decode("utf-8"),
                "sha256": sha256_bytes(PROMPT),
                "tokenization": {"add_special": True, "parse_special": True},
                "token_ids": token_ids,
                "token_count": len(token_ids),
                "final_token_index": len(token_ids) - 1,
                "final_token_id": token_ids[-1],
            },
            "capture_off": {
                "logits_b64": base64.b64encode(logits_off_raw).decode("ascii"),
                "logits_sha256": sha256_bytes(logits_off_raw),
                "argmax_token_id": argmax_off,
                "top16": off_top,
            },
            "capture_on": {
                "logits_b64": base64.b64encode(logits_on_raw).decode("ascii"),
                "logits_sha256": sha256_bytes(logits_on_raw),
                "argmax_token_id": argmax_on,
                "top16": on_top,
            },
            "hidden_state_b64": base64.b64encode(hidden_raw).decode("ascii"),
            "hidden_state_sha256": sha256_bytes(hidden_raw),
            "hidden_l2_norm": hidden_norm,
            "parity": {
                "argmax_match": argmax_off == argmax_on,
                "top16_token_ids_match": top_ids_match,
                "max_abs_logit_difference": max_difference,
                "max_abs_logit_difference_bound": MAX_LOGIT_DIFFERENCE,
                "pass": parity_pass,
            },
            "verdict": "PASS" if parity_pass else "FAIL",
        }
    finally:
        if model:
            lib.llama_model_free(model)
        if backend_initialized:
            lib.llama_backend_free()
        directory_cookie.close()


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_args() -> argparse.Namespace:
    root = ARTIFACT_DIR / "l16-hidden-state"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=QWEN_MODEL_PATH)
    parser.add_argument("--dll-dir", type=Path, default=QWEN_DLL_DIR)
    parser.add_argument("--out", type=Path, default=root / "hidden-state-capture.json")
    parser.add_argument("--context-size", type=int, default=CONTEXT_SIZE)
    parser.add_argument("--gpu-layers", type=int, default=99)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = capture_receipt(args)
        write_receipt(args.out.resolve(), receipt)
        print(json.dumps({
            "verdict": receipt["verdict"],
            "layer_index": receipt["hook"]["layer_index"],
            "hidden_l2_norm": receipt["hidden_l2_norm"],
            "max_abs_logit_difference": receipt["parity"]["max_abs_logit_difference"],
            "path": str(args.out.resolve()),
        }, indent=2))
        return 0 if receipt["verdict"] == "PASS" else 1
    except Exception as error:  # Emit a durable invalid receipt for diagnosis.
        invalid = {
            "protocol": PROTOCOL,
            "version": VERSION,
            "verdict": "INVALID",
            "reason": str(error),
        }
        try:
            write_receipt(args.out.resolve(), invalid)
        except Exception as write_error:
            print(f"failed to write INVALID receipt: {write_error}", file=sys.stderr)
        print(json.dumps(invalid, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
