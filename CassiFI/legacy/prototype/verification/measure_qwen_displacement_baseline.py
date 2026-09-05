"""Offline native Qwen-ownership baseline for :mod:`cassi_qwen_displacement`.

Two-process contract (see ``cassi_qwen_displacement`` docstring): this is the
*offline* process.  It loads the pinned Qwen GGUF into a dedicated llama.cpp
context, reads the live KV / recurrent / serialized-state / weight counters
through the focused ``llama_qwen35_footprint`` statistics API, and writes a
hash-pinned ``cassi.qwen-displacement-baseline.v1`` receipt.  That receipt
records the nonzero native Qwen ownership that *would* be present for the same
model and context — the reference the live field-only provider is measured
against.

This script never starts llama-server, never opens a socket, and never emits a
logit or token.  It is a read-only measurement of one context's ownership.

The resulting receipt is consumed by
:func:`cassi_qwen_displacement.build_field_only_displacement_receipt`, which
reports every one of these counters as exactly zero in the live field runtime.
"""

from __future__ import annotations

import argparse
import ctypes as ct
import hashlib
import json
import os
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from cassi_fi_paths import ARTIFACT_DIR, QWEN_MODEL_PATH, QWEN_ROOT
from cassi_qwen_displacement import QWEN_DISPLACEMENT_BASELINE_SCHEMA


@dataclass(frozen=True)
class Footprint:
    """Flat mirror of the native ``llama_qwen35_footprint`` struct."""
    model_size_bytes: int
    model_params: int
    n_layer_full_attn: int
    n_layer_recurrent: int
    n_layer_mtp: int
    n_vocab: int
    kv_bytes: int
    recurrent_bytes: int
    serialized_state_bytes: int
    gguf_open_count: int


class LlamaQwen35Footprint(ct.Structure):
    _fields_ = [
        ("model_size_bytes", ct.c_uint64),
        ("model_params", ct.c_uint64),
        ("n_layer_full_attn", ct.c_int32),
        ("n_layer_recurrent", ct.c_int32),
        ("n_layer_mtp", ct.c_int32),
        ("n_vocab", ct.c_int32),
        ("kv_bytes", ct.c_uint64),
        ("recurrent_bytes", ct.c_uint64),
        ("serialized_state_bytes", ct.c_uint64),
        ("gguf_open_count", ct.c_uint32),
    ]




class BaselineError(RuntimeError):
    """A checked failure while measuring the native Qwen baseline."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()

def sha256_runtime_source_tree(root: Path) -> tuple[str, tuple[str, ...]]:
    """Hash the exact public-header/core-source tree used to build ``llama.dll``.

    Relative paths and file bytes are both framed into the digest so renames,
    additions, removals, and content changes all alter the identity.
    """
    suffixes = frozenset({".c", ".cc", ".cpp", ".h", ".hpp"})
    paths = tuple(
        sorted(
            (
                path
                for source_root in (root / "include", root / "src")
                for path in source_root.rglob("*")
                if path.is_file() and path.suffix.lower() in suffixes
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )
    if not paths:
        raise BaselineError("native runtime source tree is empty")
    digest = hashlib.sha256()
    relative_paths: list[str] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        relative_bytes = relative.encode("utf-8", "strict")
        payload = path.read_bytes()
        digest.update(len(relative_bytes).to_bytes(8, "little"))
        digest.update(relative_bytes)
        digest.update(len(payload).to_bytes(8, "little"))
        digest.update(payload)
        relative_paths.append(relative)
    return digest.hexdigest(), tuple(relative_paths)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def receipt_self_hash(body: dict[str, Any]) -> str:
    canonical = {k: v for k, v in body.items() if k != "receipt_sha256"}
    return hashlib.sha256(canonical_json(canonical)).hexdigest()


def pe_export_names(path: Path) -> list[str]:
    """Return named PE exports without requiring dumpbin or an import library."""
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise BaselineError(f"{path.name} is not an MZ PE image")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise BaselineError(f"{path.name} has no PE signature")
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
        raise BaselineError(f"{path.name} has unsupported PE optional-header magic {magic:#x}")
    export_rva, export_size = struct.unpack_from("<II", data, data_directory)
    if export_rva == 0 or export_size == 0:
        raise BaselineError(f"{path.name} has no export directory")
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
        raise BaselineError(f"{path.name} export RVA {rva:#x} is outside sections")

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
            raise BaselineError(f"{path.name} has unterminated export name")
        names.append(data[name_offset:terminator].decode("ascii"))
    return names


def resolve_export(path: Path, prefix: str) -> str:
    matches = [name for name in pe_export_names(path) if name.startswith(prefix)]
    if len(matches) != 1:
        raise BaselineError(f"expected one DLL export starting with {prefix!r}, found {matches!r}")
    return matches[0]


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
        ("cassi_modal", ct.c_bool),
        ("cassi_field_step", ct.c_bool),
        ("cassi_qi_field", ct.c_bool),
        ("cassi_field_layer", ct.c_uint32),
        ("cassi_qi_field_layer", ct.c_uint32),
        ("cassi_qi_field_scales", ct.c_uint32),
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


if ct.sizeof(LlamaModelParams) != 72:
    raise RuntimeError(f"Qwen35 model params ABI is 72 bytes, got {ct.sizeof(LlamaModelParams)}")
if ct.sizeof(LlamaContextParams) != 200:
    raise RuntimeError(f"Qwen35 context params ABI is 200 bytes, got {ct.sizeof(LlamaContextParams)}")
if ct.sizeof(LlamaQwen35Footprint) != 64:
    raise RuntimeError(f"Qwen35 footprint ABI is 64 bytes, got {ct.sizeof(LlamaQwen35Footprint)}")


def configure_public_api(lib: ct.WinDLL) -> None:
    lib.llama_backend_init.argtypes = []
    lib.llama_backend_init.restype = None
    lib.llama_backend_free.argtypes = []
    lib.llama_backend_free.restype = None
    lib.llama_model_default_params.argtypes = []
    lib.llama_model_default_params.restype = LlamaModelParams
    lib.llama_context_default_params.argtypes = []
    lib.llama_context_default_params.restype = LlamaContextParams
    lib.llama_model_load_from_file.argtypes = [ct.c_char_p, LlamaModelParams]
    lib.llama_model_load_from_file.restype = ct.c_void_p
    lib.llama_model_free.argtypes = [ct.c_void_p]
    lib.llama_model_free.restype = None
    lib.llama_init_from_model.argtypes = [ct.c_void_p, LlamaContextParams]
    lib.llama_init_from_model.restype = ct.c_void_p
    lib.llama_free.argtypes = [ct.c_void_p]
    lib.llama_free.restype = None
    lib.llama_model_get_vocab.argtypes = [ct.c_void_p]
    lib.llama_model_get_vocab.restype = ct.c_void_p
    lib.llama_vocab_n_tokens.argtypes = [ct.c_void_p]
    lib.llama_vocab_n_tokens.restype = ct.c_int32


def measure_footprint(lib: ct.WinDLL, model: int, ctx: int, export: str) -> Footprint:
    fn = getattr(lib, export)
    fn.argtypes = [ct.c_void_p, ct.c_void_p, ct.POINTER(LlamaQwen35Footprint)]
    fn.restype = None
    out = LlamaQwen35Footprint()
    fn(model, ctx, ct.byref(out))
    return Footprint(
        model_size_bytes=int(out.model_size_bytes),
        model_params=int(out.model_params),
        n_layer_full_attn=int(out.n_layer_full_attn),
        n_layer_recurrent=int(out.n_layer_recurrent),
        n_layer_mtp=int(out.n_layer_mtp),
        n_vocab=int(out.n_vocab),
        kv_bytes=int(out.kv_bytes),
        recurrent_bytes=int(out.recurrent_bytes),
        serialized_state_bytes=int(out.serialized_state_bytes),
        gguf_open_count=int(out.gguf_open_count),
    )



def build_receipt(args: argparse.Namespace, footprint: Footprint) -> dict[str, Any]:
    model_path = args.model.resolve()
    runtime_dir = args.dll_dir.resolve()
    llama_path = runtime_dir / "llama.dll"

    if footprint.kv_bytes <= 0:
        raise BaselineError("baseline KV allocation is not positive — no Qwen ownership measured")
    if footprint.recurrent_bytes <= 0:
        raise BaselineError("baseline recurrent allocation is not positive — no Qwen ownership measured")
    if footprint.serialized_state_bytes <= 0:
        raise BaselineError("baseline serialized-state bytes are not positive")
    if footprint.model_size_bytes <= 0:
        raise BaselineError("baseline model size is not positive")
    if footprint.n_layer_full_attn <= 0:
        raise BaselineError("baseline full-attention layer count is not positive")
    if footprint.n_layer_recurrent <= 0:
        raise BaselineError("baseline recurrent layer count is not positive")
    if footprint.n_layer_mtp < 0:
        raise BaselineError("baseline MTP block count is negative")
    if footprint.n_vocab <= 0:
        raise BaselineError("baseline output vocabulary rows are not positive")

    reference = {
        "qwen_kv_bytes": footprint.kv_bytes,
        "qwen_recurrent_state_bytes": footprint.recurrent_bytes,
        "qwen_serialized_state_bytes": footprint.serialized_state_bytes,
        "qwen_weight_bytes_loaded": footprint.model_size_bytes,
        "qwen_layers_full_attention": footprint.n_layer_full_attn,
        "qwen_layers_recurrent": footprint.n_layer_recurrent,
        "qwen_layers_mtp": footprint.n_layer_mtp,
        "qwen_output_vocab_rows": footprint.n_vocab,
        "gguf_open_count": footprint.gguf_open_count,
    }

    identity = {
        "model_gguf_sha256": sha256_file(model_path),
        "runtime_binary_sha256": sha256_file(llama_path),
        "runtime_source_sha256": args.runtime_source_sha256,
        "model_id": model_path.name,
        "context_params": {
            "n_ctx": args.n_ctx,
            "n_batch": args.n_batch,
            "n_seq_max": 1,
            "n_gpu_layers": args.n_gpu_layers,
        },
    }
    body = {
        "schema": QWEN_DISPLACEMENT_BASELINE_SCHEMA,
        "receipt_sha256": "",
        "identity": identity,
        "reference": reference,
    }
    body["receipt_sha256"] = receipt_self_hash(body)
    return body


def measure_baseline(args: argparse.Namespace) -> dict[str, Any]:
    model_path = args.model.resolve()
    runtime_dir = args.dll_dir.resolve()
    llama_path = runtime_dir / "llama.dll"
    ggml_path = runtime_dir / "ggml.dll"
    ggml_base_path = runtime_dir / "ggml-base.dll"
    omp_candidates = (
        runtime_dir / "libomp140.x86_64.dll",
        QWEN_ROOT / "libomp140.x86_64.dll",
    )
    omp_path = next((path for path in omp_candidates if path.is_file()), None)
    for path in (model_path, llama_path, ggml_path, ggml_base_path):
        if not path.is_file():
            raise BaselineError(f"required local artifact is missing: {path}")
    if omp_path is None:
        raise BaselineError("required local artifact is missing: libomp140.x86_64.dll")

    native_root = QWEN_ROOT / "native/llama.cpp"
    runtime_source_sha256, runtime_source_files = sha256_runtime_source_tree(native_root)
    if (
        args.runtime_source_sha256 is not None
        and args.runtime_source_sha256 != runtime_source_sha256
    ):
        raise BaselineError(
            "--runtime-source-sha256 does not match the current native source tree"
        )
    args.runtime_source_sha256 = runtime_source_sha256

    footprint_export = resolve_export(llama_path, "llama_qwen35_footprint")

    directory_cookie = os.add_dll_directory(str(runtime_dir))
    backend_initialized = False
    model = 0
    ctx = 0
    try:
        ct.WinDLL(str(omp_path))
        ct.WinDLL(str(ggml_base_path))
        ggml = ct.WinDLL(str(ggml_path))
        ggml.ggml_backend_load_all_from_path.argtypes = [ct.c_char_p]
        ggml.ggml_backend_load_all_from_path.restype = None
        ggml.ggml_backend_load_all_from_path(os.fsencode(runtime_dir))

        lib = ct.WinDLL(str(llama_path))
        configure_public_api(lib)
        lib.llama_backend_init()
        backend_initialized = True

        model_params = lib.llama_model_default_params()
        model_params.n_gpu_layers = args.n_gpu_layers
        model_params.load_mtp = True
        model = int(lib.llama_model_load_from_file(os.fsencode(model_path), model_params) or 0)
        if model == 0:
            raise BaselineError("llama_model_load_from_file returned null")

        context_params = lib.llama_context_default_params()
        context_params.n_ctx = args.n_ctx
        context_params.n_batch = args.n_batch
        context_params.n_ubatch = args.n_batch
        context_params.n_seq_max = 1
        context_params.cassi_modal = False
        context_params.cassi_field_step = False
        context_params.cassi_qi_field = False
        ctx = int(lib.llama_init_from_model(model, context_params) or 0)
        if ctx == 0:
            raise BaselineError("llama_init_from_model returned null")

        footprint = measure_footprint(lib, model, ctx, footprint_export)
        receipt = build_receipt(args, footprint)
        receipt["provenance"] = {
            "llama_dll": llama_path.name,
            "llama_dll_sha256": sha256_file(llama_path),
            "ggml_dll_sha256": sha256_file(ggml_path),
            "ggml_base_dll_sha256": sha256_file(ggml_base_path),
            "openmp_dll_sha256": sha256_file(omp_path),
            "footprint_export": footprint_export,
            "model_params": footprint.model_params,
            "context_field_modes": {
                "cassi_modal": False,
                "cassi_field_step": False,
                "cassi_qi_field": False,
            },
            "runtime_source_roots": ["include", "src"],
            "runtime_source_file_count": len(runtime_source_files),
        }
        receipt["receipt_sha256"] = receipt_self_hash(receipt)
        return receipt
    finally:
        if ctx:
            lib.llama_free(ctx)
        if model:
            lib.llama_model_free(model)
        if backend_initialized:
            lib.llama_backend_free()
        directory_cookie.close()


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=QWEN_MODEL_PATH)
    parser.add_argument("--dll-dir", type=Path, default=QWEN_ROOT / "native/llama.cpp/build-cassi/bin/Release")
    parser.add_argument("--out", type=Path, default=ARTIFACT_DIR / "qwen-displacement" / "baseline-receipt.json")
    parser.add_argument("--n-ctx", type=int, default=16384)
    parser.add_argument("--n-batch", type=int, default=512)
    parser.add_argument("--n-gpu-layers", type=int, default=0)
    parser.add_argument("--runtime-source-sha256")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = measure_baseline(args)
        write_receipt(args.out.resolve(), receipt)
        print(json.dumps({
            "schema": receipt["schema"],
            "receipt_sha256": receipt["receipt_sha256"],
            "reference": receipt["reference"],
            "path": str(args.out.resolve()),
        }, indent=2, sort_keys=True))
        return 0
    except BaselineError as error:
        print(f"baseline measurement failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
