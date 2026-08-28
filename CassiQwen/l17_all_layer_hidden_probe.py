"""Capture all Qwen layer-input residuals from one local llama.cpp decode.

This is a read-only ctypes bridge for the frozen L17 protocol.  It loads only
local llama.cpp/Vulkan DLLs, enables every installed layer-input hook for one
ordinary prompt decode, copies the final prompt-token row from each layer, and
never feeds a captured value back into llama.cpp.  A fresh capture-disabled
context runs the identical token batch for the full-logit parity control.
"""

from __future__ import annotations

import argparse
import base64
import ctypes as ct
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

# Reuse only the source-verified L16 ABI/runtime helpers.  Importing this module
# does not load a DLL or execute a probe; its main() is guarded.
import l16_hidden_state_probe as l16


PROTOCOL = "CassiQwen L17 all-layer IIR field observatory"
VERSION = 1
EXPECTED_LAYER_COUNT = 64
EXPECTED_HIDDEN_DIMENSION = l16.EXPECTED_HIDDEN_DIMENSION
EXPECTED_LLAMA_VERSION = l16.EXPECTED_LLAMA_VERSION
EXPECTED_MODEL_SHA256 = l16.EXPECTED_MODEL_SHA256
CONTEXT_SIZE = l16.CONTEXT_SIZE
TOP_K = l16.TOP_K
MAX_LOGIT_DIFFERENCE = l16.MAX_LOGIT_DIFFERENCE
PROMPT = l16.PROMPT
LAYER_SET_BASENAME = l16.LAYER_SET_BASENAME
LAYER_GET_BASENAME = l16.LAYER_GET_BASENAME

ProbeError = l16.ProbeError
BatchStorage = l16.BatchStorage


def run_prompt(
    lib: Any,
    model: int,
    batch_storage: BatchStorage,
    vocabulary_size: int,
    hidden_dimension: int,
    layer_indices: list[int] | None,
    context_size: int,
    set_layer: Callable[..., None] | None,
    get_layer: Callable[..., Any] | None,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Run exactly one prompt decode and optionally copy every layer's final row.

    ``layer_indices`` is either ``None`` for the capture-off control or the
    complete ascending model layer list for the one capture-on decode.  Every
    requested hook is disabled, including hooks from a partially completed
    enable loop, before the context is freed.
    """

    context = l16.make_context(lib, model, context_size)
    result: tuple[np.ndarray, list[np.ndarray]] | None = None
    primary_error: BaseException | None = None

    try:
        if layer_indices is not None:
            if not layer_indices:
                raise ProbeError("capture-on layer list is empty")
            if set_layer is None or get_layer is None:
                raise ProbeError("all-layer capture requires both WIP hook functions")
            for layer_index in layer_indices:
                set_layer(context, layer_index, True)

        status = int(lib.llama_decode(context, batch_storage.batch))
        if status != 0:
            raise ProbeError(f"llama_decode returned {status}")

        logits_pointer = lib.llama_get_logits_ith(context, -1)
        if not logits_pointer:
            raise ProbeError("llama_get_logits_ith returned null")
        logits = np.ctypeslib.as_array(logits_pointer, shape=(vocabulary_size,)).astype(np.float32, copy=True)
        if logits.ndim != 1 or logits.size != vocabulary_size:
            raise ProbeError("llama logits shape mismatch")
        l16.assert_finite(logits, "logits")

        captured: list[np.ndarray] = []
        if layer_indices is not None:
            final_offset = (batch_storage.batch.n_tokens - 1) * hidden_dimension
            for layer_index in layer_indices:
                layer_pointer = get_layer(context, layer_index)
                if not layer_pointer:
                    raise ProbeError(f"layer {layer_index} getter returned null")
                raw_address = ct.addressof(layer_pointer.contents) + final_offset * ct.sizeof(ct.c_float)
                final_pointer = ct.cast(raw_address, ct.POINTER(ct.c_float))
                hidden = np.ctypeslib.as_array(final_pointer, shape=(hidden_dimension,)).astype(np.float32, copy=True)
                if hidden.ndim != 1 or hidden.size != hidden_dimension:
                    raise ProbeError(f"layer {layer_index} hidden state shape mismatch")
                l16.assert_finite(hidden, f"layer {layer_index} captured hidden state")
                hidden_norm = float(np.linalg.norm(hidden.astype(np.float64, copy=False)))
                if not math.isfinite(hidden_norm) or hidden_norm <= 0.0:
                    raise ProbeError(f"layer {layer_index} captured hidden state has invalid L2 norm")
                captured.append(hidden)

        result = (logits, captured)
    except BaseException as error:
        primary_error = error
    finally:
        disable_error: BaseException | None = None
        if layer_indices is not None and set_layer is not None:
            # Attempt every disable even if one call fails.  This loop runs
            # before llama_free in all cases, including a failed decode/getter.
            for layer_index in layer_indices:
                try:
                    set_layer(context, layer_index, False)
                except BaseException as error:
                    if disable_error is None:
                        disable_error = error

        free_error: BaseException | None = None
        try:
            lib.llama_free(context)
        except BaseException as error:
            free_error = error

        if primary_error is None:
            if disable_error is not None:
                primary_error = ProbeError(f"failed to disable all-layer hooks: {disable_error}")
            elif free_error is not None:
                primary_error = ProbeError(f"llama_free failed: {free_error}")

    if primary_error is not None:
        raise primary_error.with_traceback(primary_error.__traceback__)
    if result is None:
        raise ProbeError("prompt decode produced no result")
    return result


def _logit_arm(logits: np.ndarray) -> dict[str, Any]:
    raw = l16.float32_bytes(logits)
    return {
        "logits_b64": base64.b64encode(raw).decode("ascii"),
        "logits_sha256": l16.sha256_bytes(raw),
        "argmax_token_id": int(np.argmax(logits)),
        "top16": l16.top_k(logits, TOP_K),
    }


def _layer_rows(hidden_states: list[np.ndarray], layer_indices: list[int]) -> list[dict[str, Any]]:
    if len(hidden_states) != EXPECTED_LAYER_COUNT or len(layer_indices) != EXPECTED_LAYER_COUNT:
        raise ProbeError(
            f"all-layer capture returned {len(hidden_states)} rows for {len(layer_indices)} layers; "
            f"expected {EXPECTED_LAYER_COUNT}"
        )
    if layer_indices != list(range(EXPECTED_LAYER_COUNT)):
        raise ProbeError(f"layer indices are not true ascending model indices: {layer_indices!r}")

    rows: list[dict[str, Any]] = []
    for layer_index, hidden in zip(layer_indices, hidden_states, strict=True):
        if hidden.ndim != 1 or hidden.size != EXPECTED_HIDDEN_DIMENSION:
            raise ProbeError(f"layer {layer_index} hidden width mismatch")
        l16.assert_finite(hidden, f"layer {layer_index} hidden state")
        raw = l16.float32_bytes(hidden)
        if len(raw) != EXPECTED_HIDDEN_DIMENSION * 4:
            raise ProbeError(f"layer {layer_index} hidden byte length mismatch")
        hidden_norm = float(np.linalg.norm(hidden.astype(np.float64, copy=False)))
        if not math.isfinite(hidden_norm) or hidden_norm <= 0.0:
            raise ProbeError(f"layer {layer_index} hidden L2 norm is invalid")
        rows.append(
            {
                "layer_index": layer_index,
                "hidden_state_b64": base64.b64encode(raw).decode("ascii"),
                "hidden_state_sha256": l16.sha256_bytes(raw),
                "hidden_l2_norm": hidden_norm,
            }
        )
    return rows


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
        raise ProbeError(f"L17 freezes context_size={CONTEXT_SIZE}, got {args.context_size}")
    if args.gpu_layers != 99:
        raise ProbeError("L17 freezes gpu_layers=99")

    model_hash = l16.sha256_file(model_path)
    if model_hash != EXPECTED_MODEL_SHA256:
        raise ProbeError(f"GGUF SHA-256 mismatch: {model_hash}")
    hook_names = l16.resolve_wip_hook_names(llama_path)

    # The cookie must live through all sibling DLL loads; no global PATH edit.
    directory_cookie = os.add_dll_directory(str(runtime_dir))
    backend_initialized = False
    model = 0
    lib: Any = None
    try:
        # b10472's ggml-base imports OpenMP and ggml imports the base DLL.
        ct.WinDLL(str(omp_path))
        ct.WinDLL(str(ggml_base_path))
        ggml = ct.WinDLL(str(ggml_path))
        ggml.ggml_backend_load_all_from_path.argtypes = [ct.c_char_p]
        ggml.ggml_backend_load_all_from_path.restype = None
        ggml.ggml_backend_load_all_from_path(os.fsencode(runtime_dir))

        lib = ct.WinDLL(str(llama_path))
        l16.configure_public_api(lib)
        set_layer, get_layer = l16.configure_wip_hooks(lib, hook_names)
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
        if layer_count != EXPECTED_LAYER_COUNT:
            raise ProbeError(f"model layer count mismatch: {layer_count}; expected {EXPECTED_LAYER_COUNT}")
        layer_indices = list(range(layer_count))

        vocabulary = int(lib.llama_model_get_vocab(model) or 0)
        if vocabulary == 0:
            raise ProbeError("llama_model_get_vocab returned null")
        vocabulary_size = int(lib.llama_vocab_n_tokens(vocabulary))
        if vocabulary_size <= 0:
            raise ProbeError(f"model vocabulary size is invalid: {vocabulary_size}")

        token_ids = l16.tokenize(lib, vocabulary, PROMPT)
        if len(token_ids) > args.context_size:
            raise ProbeError(f"prompt has {len(token_ids)} tokens, exceeds context {args.context_size}")
        batch_storage = l16.build_batch(token_ids)

        # The two calls use the same token batch and loaded model.  The
        # capture-on call is exactly one decode with every layer enabled.
        logits_off, no_hidden = run_prompt(
            lib,
            model,
            batch_storage,
            vocabulary_size,
            hidden_dimension,
            None,
            args.context_size,
            None,
            None,
        )
        if no_hidden:
            raise ProbeError("capture-off execution unexpectedly returned hidden states")
        logits_on, hidden_states = run_prompt(
            lib,
            model,
            batch_storage,
            vocabulary_size,
            hidden_dimension,
            layer_indices,
            args.context_size,
            set_layer,
            get_layer,
        )
        layers = _layer_rows(hidden_states, layer_indices)

        capture_off = _logit_arm(logits_off)
        capture_on = _logit_arm(logits_on)
        off_ids = [row["token_id"] for row in capture_off["top16"]]
        on_ids = [row["token_id"] for row in capture_on["top16"]]
        max_difference = float(
            np.max(np.abs(logits_off.astype(np.float64, copy=False) - logits_on.astype(np.float64, copy=False)))
        )
        argmax_match = capture_off["argmax_token_id"] == capture_on["argmax_token_id"]
        top_ids_match = off_ids == on_ids
        parity_pass = argmax_match and top_ids_match and max_difference <= MAX_LOGIT_DIFFERENCE

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
                "llama_dll_sha256": l16.sha256_file(llama_path),
                "ggml_dll": ggml_path.name,
                "ggml_dll_sha256": l16.sha256_file(ggml_path),
                "llama_version": version,
                "package_build": 10472,
                "ggml_base_dll": ggml_base_path.name,
                "ggml_base_dll_sha256": l16.sha256_file(ggml_base_path),
                "package_commit": "60eeeb608",
                "openmp_dll": omp_path.name,
                "openmp_dll_sha256": l16.sha256_file(omp_path),
                "backend_loader": "ggml_backend_load_all_from_path",
                "backend_path": runtime_dir.name,
                "requested_gpu_layers": args.gpu_layers,
                "context_size": args.context_size,
                "batch_size": args.context_size,
            },
            "hook": {
                "kind": "all_layer_input_residuals",
                "layer_rule": "0..n_layer-1",
                "layer_indices": layer_indices,
                "token_row": len(token_ids) - 1,
                "setter_export": hook_names[LAYER_SET_BASENAME],
                "getter_export": hook_names[LAYER_GET_BASENAME],
                "source": "llama.cpp 60eeeb608 src/llama-ext.h",
            },
            "prompt": {
                "utf8": PROMPT.decode("utf-8"),
                "sha256": l16.sha256_bytes(PROMPT),
                "tokenization": {"add_special": True, "parse_special": True},
                "token_ids": token_ids,
                "token_count": len(token_ids),
                "final_token_index": len(token_ids) - 1,
                "final_token_id": token_ids[-1],
            },
            "capture_off": capture_off,
            "capture_on": capture_on,
            "layers": layers,
            "parity": {
                "argmax_match": argmax_match,
                "top16_token_ids_match": top_ids_match,
                "max_abs_logit_difference": max_difference,
                "max_abs_logit_difference_bound": MAX_LOGIT_DIFFERENCE,
                "pass": parity_pass,
            },
            "verdict": "PASS" if parity_pass else "FAIL",
        }
    finally:
        model_error: BaseException | None = None
        backend_error: BaseException | None = None
        try:
            if model and lib is not None:
                try:
                    lib.llama_model_free(model)
                except BaseException as error:
                    model_error = error
        finally:
            try:
                if backend_initialized and lib is not None:
                    try:
                        lib.llama_backend_free()
                    except BaseException as error:
                        backend_error = error
            finally:
                directory_cookie.close()
        if model_error is not None:
            raise ProbeError(f"llama_model_free failed: {model_error}")
        if backend_error is not None:
            raise ProbeError(f"llama_backend_free failed: {backend_error}")


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON atomically beside the requested path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=root / "Qwen3.8-27B-Q4_K_M.gguf")
    parser.add_argument("--dll-dir", type=Path, default=root)
    parser.add_argument("--out", type=Path, default=root / "all-layer-hidden-state-capture.json")
    parser.add_argument("--context-size", type=int, default=CONTEXT_SIZE)
    parser.add_argument("--gpu-layers", type=int, default=99)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = capture_receipt(args)
        write_receipt(args.out.resolve(), receipt)
        print(
            json.dumps(
                {
                    "verdict": receipt["verdict"],
                    "layer_count": receipt["model"]["layer_count"],
                    "token_row": receipt["hook"]["token_row"],
                    "max_abs_logit_difference": receipt["parity"]["max_abs_logit_difference"],
                    "path": str(args.out.resolve()),
                },
                indent=2,
            )
        )
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
