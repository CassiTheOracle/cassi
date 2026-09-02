"""Run local Qwen with canonical Cassi field control at every trunk layer.

The Qwen trunk, hybrid memory, LM head, and greedy token choice remain intact.
The canonical Cassi field is the only adaptive controller: each decode captures
all layer-input residuals, maps them through one per-request working field, and
installs the resulting layer-specific control vector for the next decode.
"""

from __future__ import annotations

import argparse
import ctypes as ct
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import l16_hidden_state_probe as l16
from cassi_field_language import CassiQiTextEngine
from cassi_fi_paths import QWEN_DLL_DIR, QWEN_MODEL_PATH
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState

PROTOCOL = "CassiFI canonical-field Qwen control"
VERSION = 3
EXPECTED_MODEL_SHA256 = l16.EXPECTED_MODEL_SHA256
EXPECTED_HIDDEN_DIMENSION = 5120
EXPECTED_LAYER_COUNT = 64
CONTROLLED_LAYER_COUNT = EXPECTED_LAYER_COUNT - 1
DEFAULT_CONFIG = ROOT / "configs" / "cassi-qi-corpus-language.json"
DEFAULT_CHECKPOINT = ROOT / "artifacts" / "cassi-qi-temporal-language" / "field-state.pt"
DEFAULT_RECEIPT = QWEN_DLL_DIR / "_diag" / "canonical-field-control.json"
DEFAULT_PROMPT = "Explain in one sentence why a compass points north."
DEFAULT_COUPLING = 0.02


class FieldControlError(RuntimeError):
    pass


@dataclass
class DecodeResult:
    logits: np.ndarray
    hidden: np.ndarray | None


@dataclass
class GenerationResult:
    token_ids: list[int]
    pieces: list[bytes]
    logits: list[np.ndarray]
    first_hidden: np.ndarray | None
    control_events: list[dict[str, Any]]

    @property
    def raw(self) -> bytes:
        return b"".join(self.pieces)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _f32_bytes(value: np.ndarray) -> bytes:
    return np.ascontiguousarray(value, dtype="<f4").tobytes(order="C")


def _state_sha256(state: QiFieldState) -> str:
    raw = state.field.detach().to(device="cpu", dtype=torch.float32).contiguous().numpy().astype("<f4", copy=False).tobytes()
    return _sha256_bytes(raw)


def _load_engine(config_path: Path, checkpoint_path: Path) -> CassiQiTextEngine:
    try:
        config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FieldControlError(f"cannot load field configuration: {error}") from error
    controller = QiFieldController(QiFieldConfig.from_dict(config_payload))
    engine = CassiQiTextEngine(controller, checkpoint_path=checkpoint_path)
    if controller.config.mode_count != 6144 or controller.config.wave_mode_count != 3072:
        raise FieldControlError("field control requires the canonical M=6144 language profile")
    return engine


def _prime_field(engine: CassiQiTextEngine, prompt: str) -> QiFieldState:
    state = engine.initial_state(device="cpu", dtype=torch.float32)
    symbols = engine.codec.encode_messages(({"role": "user", "content": prompt},)) + (engine.codec.assistant_symbol,)
    for symbol in symbols:
        state, _ = engine.law.sense_event(state, symbol)
    if engine.law.memory_sha256(state) != engine.corpus_memory_sha256:
        raise FieldControlError("prompt priming changed trained field memory")
    return state

def _sense_qwen_output(
    engine: CassiQiTextEngine,
    state: QiFieldState,
    piece: bytes,
    *,
    end_turn: bool,
) -> tuple[QiFieldState, dict[str, Any]]:
    symbols = (engine.codec.end_turn_symbol,) if end_turn else tuple(piece)
    before = _state_sha256(state)
    successor = state
    for symbol in symbols:
        successor, _ = engine.law.sense_event(successor, symbol)
    if engine.law.memory_sha256(successor) != engine.corpus_memory_sha256:
        raise FieldControlError("Qwen output transition changed trained field memory")
    return successor, {
        "direction": "qwen_output_to_field",
        "symbol_count": len(symbols),
        "symbols_sha256": _sha256_bytes(bytes(symbols)) if symbols and max(symbols) < 256 else _sha256_bytes(
            json.dumps(symbols, separators=(",", ":")).encode("ascii")
        ),
        "end_turn": end_turn,
        "state_before_sha256": before,
        "state_after_sha256": _state_sha256(successor),
    }



def _hidden_to_waves(hidden: np.ndarray, wave_mode_count: int) -> tuple[torch.Tensor, np.ndarray, float]:
    if hidden.ndim != 2 or hidden.shape[1] != EXPECTED_HIDDEN_DIMENSION:
        raise FieldControlError(f"hidden residuals must have shape [L, {EXPECTED_HIDDEN_DIMENSION}]")
    if not np.isfinite(hidden).all():
        raise FieldControlError("hidden residuals contain non-finite values")
    norms = np.linalg.norm(hidden.astype(np.float64), axis=1)
    if not np.isfinite(norms).all() or np.any(norms <= 0.0):
        raise FieldControlError("hidden residual norms must be finite and positive")
    directions = hidden.astype(np.float64) / norms[:, None]
    occupied = EXPECTED_HIDDEN_DIMENSION // 2
    if occupied > wave_mode_count:
        raise FieldControlError("field wave boundary is narrower than the Qwen residual")
    waves = torch.zeros((hidden.shape[0], wave_mode_count, 2), dtype=torch.float32)
    waves[:, :occupied, :] = torch.from_numpy(directions.astype(np.float32).reshape(hidden.shape[0], occupied, 2))
    recovered = waves[:, :occupied, :].reshape(hidden.shape).numpy().astype(np.float64)
    boundary_error = float(np.max(np.abs(recovered - directions)))
    return waves, norms, boundary_error


def _layer_controls(
    engine: CassiQiTextEngine,
    state: QiFieldState,
    hidden: np.ndarray,
    coupling: float,
    commit_layer: int,
) -> tuple[QiFieldState, np.ndarray, dict[str, Any]]:
    if not math.isfinite(coupling) or not 0.0 <= coupling <= 1.0:
        raise FieldControlError("coupling must lie in [0, 1]")
    layer_count = hidden.shape[0]
    if not 0 <= commit_layer < layer_count:
        raise FieldControlError("commit layer is outside the captured layer range")

    waves, hidden_norms, boundary_error = _hidden_to_waves(
        hidden, engine.controller.config.wave_mode_count
    )
    batched = QiFieldState(state.field.repeat(1, 1, layer_count).contiguous())
    sensed = engine.controller.sense_wave(
        batched,
        waves,
        structured_source=torch.ones(layer_count, dtype=torch.float32),
    )
    if not isinstance(sensed, QiFieldState):
        raise FieldControlError(
            "field sense unexpectedly returned diagnostics instead of state"
        )

    # The canonical trajectory memory has its own explicit 260-port readout.
    # controller.emit() is a separate gated Qi-symbol boundary and is allowed
    # to abstain; it is not repurposed as an arbitrary residual decoder.
    port_scores = torch.stack(
        [
            engine.law.port_scores(
                QiFieldState(sensed.field[..., layer : layer + 1])
            )
            for layer in range(layer_count)
        ],
        dim=0,
    )
    score_norms = torch.linalg.vector_norm(port_scores, dim=1)
    available = torch.isfinite(score_norms) & (score_norms > 0.0)
    weights = torch.where(
        available[:, None],
        port_scores
        / torch.clamp_min(
            score_norms[:, None], torch.finfo(torch.float32).eps
        ),
        torch.zeros_like(port_scores),
    )
    codebook = engine.controller.codebook(
        0, device=state.field.device, dtype=torch.float32
    )
    port_waves = torch.einsum("la,amc->lmc", weights, codebook)
    occupied = EXPECTED_HIDDEN_DIMENSION // 2
    decoded = port_waves[:, :occupied, :].reshape(
        layer_count, EXPECTED_HIDDEN_DIMENSION
    )
    decoded_norms = torch.linalg.vector_norm(decoded, dim=1)
    usable = available & torch.isfinite(decoded_norms) & (decoded_norms > 0.0)
    unit = torch.where(
        usable[:, None],
        decoded
        / torch.clamp_min(
            decoded_norms[:, None], torch.finfo(torch.float32).eps
        ),
        torch.zeros_like(decoded),
    )
    controls = (
        unit.numpy()
        * hidden_norms[:, None].astype(np.float32)
        * np.float32(coupling)
    )
    controls = np.ascontiguousarray(controls[1:, :], dtype=np.float32)
    if not np.isfinite(controls).all():
        raise FieldControlError("field produced a non-finite control vector")

    committed = QiFieldState(
        sensed.field[..., commit_layer : commit_layer + 1].clone().contiguous()
    )
    committed = engine.law.dwell(committed)
    memory_sha256 = engine.law.memory_sha256(committed)
    if memory_sha256 != engine.corpus_memory_sha256:
        raise FieldControlError(
            "field control changed trained trajectory memory"
        )

    active_rows = np.linalg.norm(controls.astype(np.float64), axis=1) > 0.0
    event = {
        "readout": "canonical_trajectory_memory_ports",
        "state_before_sha256": _state_sha256(state),
        "state_after_sha256": _state_sha256(committed),
        "memory_sha256": memory_sha256,
        "hidden_sha256": _sha256_bytes(_f32_bytes(hidden)),
        "hidden_l2_min": float(hidden_norms.min()),
        "hidden_l2_max": float(hidden_norms.max()),
        "boundary_roundtrip_max_abs": boundary_error,
        "control_sha256": _sha256_bytes(_f32_bytes(controls)),
        "control_l2": float(np.linalg.norm(controls.astype(np.float64))),
        "control_max_abs": float(np.max(np.abs(controls))),
        "active_control_layers": int(active_rows.sum()),
        "available_field_layers": int(available.sum().item()),
        "commit_layer": commit_layer,
        "commit_port_score_max": float(port_scores[commit_layer].max().item()),
        "commit_port_score_nonzero": int(
            torch.count_nonzero(port_scores[commit_layer]).item()
        ),
    }
    return committed, controls, event


def _build_batch(tokens: list[int], start_position: int) -> l16.BatchStorage:
    if not tokens or start_position < 0:
        raise FieldControlError("decode batch requires tokens and a non-negative position")
    count = len(tokens)
    token_values = (ct.c_int32 * count)(*tokens)
    position_values = (ct.c_int32 * count)(*(start_position + index for index in range(count)))
    n_seq_values = (ct.c_int32 * count)(*([1] * count))
    sequence_values = (ct.c_int32 * count)(*([0] * count))
    sequence_pointers = (ct.POINTER(ct.c_int32) * count)()
    for index in range(count):
        sequence_pointers[index] = ct.cast(
            ct.byref(sequence_values, index * ct.sizeof(ct.c_int32)), ct.POINTER(ct.c_int32)
        )
    logit_values = (ct.c_int8 * count)()
    logit_values[count - 1] = 1
    batch = l16.LlamaBatch(
        n_tokens=count,
        token=token_values,
        embd=ct.POINTER(ct.c_float)(),
        pos=position_values,
        n_seq_id=n_seq_values,
        seq_id=sequence_pointers,
        logits=logit_values,
    )
    return l16.BatchStorage(
        batch,
        token_values,
        position_values,
        n_seq_values,
        sequence_values,
        sequence_pointers,
        logit_values,
    )


def _configure_extra_api(lib: ct.WinDLL) -> None:
    lib.llama_set_adapter_cvec.argtypes = [
        ct.c_void_p,
        ct.POINTER(ct.c_float),
        ct.c_size_t,
        ct.c_int32,
        ct.c_int32,
        ct.c_int32,
    ]
    lib.llama_set_adapter_cvec.restype = ct.c_int32
    lib.llama_vocab_is_eog.argtypes = [ct.c_void_p, ct.c_int32]
    lib.llama_vocab_is_eog.restype = ct.c_bool
    lib.llama_token_to_piece.argtypes = [
        ct.c_void_p,
        ct.c_int32,
        ct.POINTER(ct.c_char),
        ct.c_int32,
        ct.c_int32,
        ct.c_bool,
    ]
    lib.llama_token_to_piece.restype = ct.c_int32


def _apply_controls(lib: ct.WinDLL, context: int, controls: np.ndarray) -> None:
    if controls.shape != (CONTROLLED_LAYER_COUNT, EXPECTED_HIDDEN_DIMENSION):
        raise FieldControlError("control-vector shape mismatch")
    result = int(
        lib.llama_set_adapter_cvec(
            context,
            controls.ctypes.data_as(ct.POINTER(ct.c_float)),
            controls.size,
            EXPECTED_HIDDEN_DIMENSION,
            1,
            CONTROLLED_LAYER_COUNT,
        )
    )
    if result != 0:
        raise FieldControlError(f"llama_set_adapter_cvec returned {result}")


def _token_piece(lib: ct.WinDLL, vocab: int, token: int) -> bytes:
    capacity = 64
    while True:
        buffer = (ct.c_char * capacity)()
        count = int(lib.llama_token_to_piece(vocab, token, buffer, capacity, 0, False))
        if count >= 0:
            return bytes(buffer[:count])
        capacity = -count
        if capacity <= 0 or capacity > 1 << 20:
            raise FieldControlError("token piece requested an invalid buffer size")


def _decode(
    lib: ct.WinDLL,
    context: int,
    batch: l16.BatchStorage,
    vocabulary_size: int,
    get_layer: Callable[..., Any] | None,
) -> DecodeResult:
    status = int(lib.llama_decode(context, batch.batch))
    if status != 0:
        raise FieldControlError(f"llama_decode returned {status}")
    logits_pointer = lib.llama_get_logits_ith(context, -1)
    if not logits_pointer:
        raise FieldControlError("llama_get_logits_ith returned null")
    logits = np.ctypeslib.as_array(logits_pointer, shape=(vocabulary_size,)).astype(np.float32, copy=True)
    if not np.isfinite(logits).all():
        raise FieldControlError("Qwen logits contain non-finite values")

    hidden: np.ndarray | None = None
    if get_layer is not None:
        hidden = np.empty((EXPECTED_LAYER_COUNT, EXPECTED_HIDDEN_DIMENSION), dtype=np.float32)
        final_row = batch.batch.n_tokens - 1
        for layer in range(EXPECTED_LAYER_COUNT):
            pointer = get_layer(context, layer)
            if not pointer:
                raise FieldControlError(f"layer {layer} capture returned null")
            offset = final_row * EXPECTED_HIDDEN_DIMENSION
            address = ct.addressof(pointer.contents) + offset * ct.sizeof(ct.c_float)
            row_pointer = ct.cast(address, ct.POINTER(ct.c_float))
            hidden[layer] = np.ctypeslib.as_array(row_pointer, shape=(EXPECTED_HIDDEN_DIMENSION,))
        if not np.isfinite(hidden).all():
            raise FieldControlError("captured Qwen residuals contain non-finite values")
    return DecodeResult(logits, hidden)


def _generate(
    lib: ct.WinDLL,
    model: int,
    vocab: int,
    vocabulary_size: int,
    prompt_tokens: list[int],
    context_size: int,
    max_tokens: int,
    set_layer: Callable[..., None] | None,
    get_layer: Callable[..., Any] | None,
    initial_controls: np.ndarray | None = None,
    controller: Callable[[np.ndarray, bytes, bool], tuple[np.ndarray, dict[str, Any]]] | None = None,
) -> GenerationResult:
    context = l16.make_context(lib, model, context_size)
    capture = set_layer is not None
    try:
        if capture:
            if get_layer is None:
                raise FieldControlError("capture getter is absent")
            for layer in range(EXPECTED_LAYER_COUNT):
                set_layer(context, layer, True)
        if initial_controls is not None:
            _apply_controls(lib, context, initial_controls)

        decode = _decode(
            lib,
            context,
            _build_batch(prompt_tokens, 0),
            vocabulary_size,
            get_layer if capture else None,
        )
        first_hidden = None if decode.hidden is None else decode.hidden.copy()
        token_ids: list[int] = []
        pieces: list[bytes] = []
        logits_rows: list[np.ndarray] = []
        control_events: list[dict[str, Any]] = []
        position = len(prompt_tokens)

        for _ in range(max_tokens):
            logits_rows.append(decode.logits)
            token = int(np.argmax(decode.logits))
            token_ids.append(token)
            end_turn = bool(lib.llama_vocab_is_eog(vocab, token))
            piece = b"" if end_turn else _token_piece(lib, vocab, token)
            if not end_turn:
                pieces.append(piece)
            if controller is not None:
                if decode.hidden is None:
                    raise FieldControlError(
                        "field controller requires captured residuals"
                    )
                controls, event = controller(decode.hidden, piece, end_turn)
                _apply_controls(lib, context, controls)
                control_events.append(event)
            if end_turn or len(token_ids) >= max_tokens:
                break
            decode = _decode(
                lib,
                context,
                _build_batch([token], position),
                vocabulary_size,
                get_layer if capture else None,
            )
            position += 1

        return GenerationResult(token_ids, pieces, logits_rows, first_hidden, control_events)
    finally:
        if capture:
            for layer in range(EXPECTED_LAYER_COUNT):
                try:
                    set_layer(context, layer, False)
                except Exception:
                    pass
        lib.llama_free(context)


def _generation_receipt(result: GenerationResult) -> dict[str, Any]:
    return {
        "token_ids": result.token_ids,
        "pieces_utf8": [piece.decode("utf-8", errors="replace") for piece in result.pieces],
        "output_utf8": result.raw.decode("utf-8", errors="replace"),
        "output_sha256": _sha256_bytes(result.raw),
        "logits_sha256": [_sha256_bytes(_f32_bytes(row)) for row in result.logits],
        "control_events": result.control_events,
    }


def _max_logit_difference(left: GenerationResult, right: GenerationResult) -> float:
    if len(left.logits) != len(right.logits):
        return math.inf
    return max(
        (float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64)))) for a, b in zip(left.logits, right.logits)),
        default=0.0,
    )


def _run(args: argparse.Namespace) -> dict[str, Any]:
    model_path = args.model.resolve()
    dll_dir = args.dll_dir.resolve()
    checkpoint_path = args.checkpoint.resolve()
    config_path = args.config.resolve()
    llama_path = dll_dir / "llama.dll"
    dependencies = [
        dll_dir / "libomp140.x86_64.dll",
        dll_dir / "ggml-base.dll",
        dll_dir / "ggml.dll",
        llama_path,
        model_path,
        checkpoint_path,
        config_path,
    ]
    for path in dependencies:
        if not path.is_file():
            raise FieldControlError(f"required artifact is missing: {path}")
    if l16.sha256_file(model_path) != EXPECTED_MODEL_SHA256:
        raise FieldControlError("local Qwen GGUF hash does not match the pinned model")
    if args.max_tokens < 1 or args.context_size < args.max_tokens + 8:
        raise FieldControlError("context or output token bound is invalid")

    engine = _load_engine(config_path, checkpoint_path)
    checkpoint_hash_before = l16.sha256_file(checkpoint_path)
    primed_state = _prime_field(engine, args.prompt)
    initial_state_sha256 = _state_sha256(primed_state)

    hook_names = l16.resolve_wip_hook_names(llama_path)
    directory_cookie = os.add_dll_directory(str(dll_dir))
    backend_initialized = False
    model = 0
    lib: Any = None
    try:
        ct.WinDLL(str(dll_dir / "libomp140.x86_64.dll"))
        ct.WinDLL(str(dll_dir / "ggml-base.dll"))
        ggml = ct.WinDLL(str(dll_dir / "ggml.dll"))
        ggml.ggml_backend_load_all_from_path.argtypes = [ct.c_char_p]
        ggml.ggml_backend_load_all_from_path.restype = None
        ggml.ggml_backend_load_all_from_path(os.fsencode(dll_dir))

        lib = ct.WinDLL(str(llama_path))
        l16.configure_public_api(lib)
        _configure_extra_api(lib)
        set_layer, get_layer = l16.configure_wip_hooks(lib, hook_names)
        version = (lib.llama_version() or b"").decode("utf-8")
        if version != l16.EXPECTED_LLAMA_VERSION:
            raise FieldControlError(f"llama runtime version mismatch: {version!r}")
        lib.llama_backend_init()
        backend_initialized = True

        model_params = lib.llama_model_default_params()
        model_params.n_gpu_layers = args.gpu_layers
        model = int(lib.llama_model_load_from_file(os.fsencode(model_path), model_params) or 0)
        if model == 0:
            raise FieldControlError("llama_model_load_from_file returned null")
        hidden_dimension = int(lib.llama_model_n_embd(model))
        layer_count = int(lib.llama_model_n_layer(model))
        if hidden_dimension != EXPECTED_HIDDEN_DIMENSION or layer_count != EXPECTED_LAYER_COUNT:
            raise FieldControlError(
                f"Qwen shape mismatch: hidden={hidden_dimension}, layers={layer_count}"
            )
        vocab = int(lib.llama_model_get_vocab(model) or 0)
        vocabulary_size = int(lib.llama_vocab_n_tokens(vocab))
        prompt_bytes = args.prompt.encode("utf-8")
        prompt_tokens = l16.tokenize(lib, vocab, prompt_bytes)
        if len(prompt_tokens) + args.max_tokens > args.context_size:
            raise FieldControlError("prompt and output exceed the context bound")

        baseline = _generate(
            lib,
            model,
            vocab,
            vocabulary_size,
            prompt_tokens,
            args.context_size,
            args.max_tokens,
            None,
            None,
        )
        zero_controls = np.zeros((CONTROLLED_LAYER_COUNT, hidden_dimension), dtype=np.float32)
        zero = _generate(
            lib,
            model,
            vocab,
            vocabulary_size,
            prompt_tokens,
            args.context_size,
            args.max_tokens,
            set_layer,
            get_layer,
            initial_controls=zero_controls,
            controller=lambda _hidden, piece, end_turn: (
                zero_controls,
                {
                    "control_sha256": _sha256_bytes(
                        _f32_bytes(zero_controls)
                    ),
                    "control_update_scheduled": True,
                    "output_bytes": len(piece),
                    "end_turn": end_turn,
                },
            ),
        )
        if zero.first_hidden is None:
            raise FieldControlError("zero-control run did not capture prompt residuals")
        bootstrap_state, bootstrap_controls, bootstrap_event = _layer_controls(
            engine,
            primed_state,
            zero.first_hidden,
            args.coupling,
            args.commit_layer,
        )

        working_state = bootstrap_state

        def field_controller(
            hidden: np.ndarray, piece: bytes, end_turn: bool
        ) -> tuple[np.ndarray, dict[str, Any]]:
            nonlocal working_state
            working_state, output_transition = _sense_qwen_output(
                engine, working_state, piece, end_turn=end_turn
            )
            working_state, controls, event = _layer_controls(
                engine,
                working_state,
                hidden,
                args.coupling,
                args.commit_layer,
            )
            event["output_transition"] = output_transition
            return controls, event

        field = _generate(
            lib,
            model,
            vocab,
            vocabulary_size,
            prompt_tokens,
            args.context_size,
            args.max_tokens,
            set_layer,
            get_layer,
            initial_controls=bootstrap_controls,
            controller=field_controller,
        )

        zero_max_difference = _max_logit_difference(baseline, zero)
        zero_parity = (
            baseline.token_ids == zero.token_ids
            and zero_max_difference <= l16.MAX_LOGIT_DIFFERENCE
        )
        initial_field_difference = float(
            np.max(np.abs(field.logits[0].astype(np.float64) - baseline.logits[0].astype(np.float64)))
        )
        first_divergence = next(
            (
                index
                for index, pair in enumerate(zip(baseline.token_ids, field.token_ids))
                if pair[0] != pair[1]
            ),
            None,
        )
        field_control_nonzero = bootstrap_event["control_l2"] > 0.0 and all(
            event["control_l2"] > 0.0 for event in field.control_events
        )
        memory_preserved = engine.law.memory_sha256(working_state) == engine.corpus_memory_sha256
        checkpoint_hash_after = l16.sha256_file(checkpoint_path)
        checkpoint_unchanged = checkpoint_hash_before == checkpoint_hash_after
        verdict = (
            "PASS"
            if zero_parity
            and field_control_nonzero
            and initial_field_difference > l16.MAX_LOGIT_DIFFERENCE
            and memory_preserved
            and checkpoint_unchanged
            else "FAIL"
        )

        return {
            "protocol": PROTOCOL,
            "version": VERSION,
            "verdict": verdict,
            "scope": "additive Python canonical-field steering over a fixed Qwen trunk",
            "model": {
                "path": str(model_path),
                "sha256": EXPECTED_MODEL_SHA256,
                "hidden_dimension": hidden_dimension,
                "layer_count": layer_count,
                "vocabulary_size": vocabulary_size,
            },
            "runtime": {
                "llama_version": version,
                "llama_dll_sha256": l16.sha256_file(llama_path),
                "ggml_dll_sha256": l16.sha256_file(dll_dir / "ggml.dll"),
                "gpu_layers_requested": args.gpu_layers,
                "context_size": args.context_size,
                "capture_exports": hook_names,
                "control_export": "llama_set_adapter_cvec",
                "llama_dll_rebuilt_for_runner": False,
                "native_sources_modified": False,
                "native_verification": "pre-existing pinned DLL API smoke; no source-to-binary rebuild evidence",
            },
            "field": {
                "checkpoint_sha256": checkpoint_hash_before,
                "checkpoint_unchanged": checkpoint_unchanged,
                "config_fingerprint": engine.controller.config_fingerprint,
                "codebook_fingerprint": engine.controller.codebook_fingerprint,
                "codec_fingerprint": engine.codec.fingerprint,
                "trained_memory_sha256": engine.corpus_memory_sha256,
                "trained_memory_preserved": memory_preserved,
                "initial_state_sha256": initial_state_sha256,
                "final_state_sha256": _state_sha256(working_state),
                "state_shape": list(working_state.field.shape),
                "working_state_policy": "per-request clone; no consolidation or checkpoint write",
            },
            "control": {
                "coupling": args.coupling,
                "commit_layer": args.commit_layer,
                "bootstrap": bootstrap_event,
                "layer_range_inclusive": [1, CONTROLLED_LAYER_COUNT],
                "application": "context control vector after native layers 1 through 63",
                "timing": "sample output into field, set cvec, then consume it on the next llama_decode",
            },
            "ownership": {
                "class": "additive_graph_steering_rung_1",
                "field_controlled_layers": CONTROLLED_LAYER_COUNT,
                "qwen_weight_bytes_modified": 0,
                "qwen_weight_bytes_touched_per_token": None,
                "qwen_weight_bytes_touched_per_token_status": "not measured; the unchanged full native Qwen trunk executes every decode",
                "native_dynamic_state_bytes_removed": 0,
                "native_ops_skipped": 0,
                "native_layers_replaced": 0,
                "lm_head_rows_replaced": 0,
                "qwen_kv_recurrent_tokenizer_and_lm_head_retained": True,
            },
            "prompt": {
                "utf8": args.prompt,
                "sha256": _sha256_bytes(prompt_bytes),
                "token_ids": prompt_tokens,
            },
            "baseline": _generation_receipt(baseline),
            "zero_control": _generation_receipt(zero),
            "field_control": _generation_receipt(field),
            "comparison": {
                "zero_control_max_abs_logit_difference": zero_max_difference,
                "zero_control_parity": zero_parity,
                "initial_field_max_abs_logit_difference": initial_field_difference,
                "first_token_divergence_index": first_divergence,
                "field_control_nonzero": field_control_nonzero,
            },
        }
    finally:
        if model and lib is not None:
            lib.llama_model_free(model)
        if backend_initialized and lib is not None:
            lib.llama_backend_free()
        directory_cookie.close()


def _self_check(config: Path, checkpoint: Path) -> None:
    engine = _load_engine(config.resolve(), checkpoint.resolve())
    state = _prime_field(engine, "field control self-check")
    generator = np.random.default_rng(0xCA551)
    hidden = generator.standard_normal((EXPECTED_LAYER_COUNT, EXPECTED_HIDDEN_DIMENSION), dtype=np.float32)
    first_state, first_controls, first_event = _layer_controls(engine, state, hidden, 0.05, 32)
    second_state, second_controls, second_event = _layer_controls(engine, state, hidden, 0.05, 32)
    if not np.array_equal(first_controls, second_controls):
        raise FieldControlError("field control self-check is not deterministic")
    if _state_sha256(first_state) != _state_sha256(second_state):
        raise FieldControlError("field successor self-check is not deterministic")
    if first_event != second_event:
        raise FieldControlError("field receipt self-check is not deterministic")
    if first_event["boundary_roundtrip_max_abs"] > 1.0e-7:
        raise FieldControlError("residual boundary round trip exceeds float32 tolerance")
    if first_event["control_l2"] <= 0.0 or first_event["active_control_layers"] < 1:
        raise FieldControlError("field control self-check produced no intervention")
    if engine.law.memory_sha256(first_state) != engine.corpus_memory_sha256:
        raise FieldControlError("field control self-check changed trained memory")
    print(
        json.dumps(
            {
                "verdict": "PASS",
                "state_sha256": _state_sha256(first_state),
                "control_sha256": first_event["control_sha256"],
                "control_l2": first_event["control_l2"],
                "boundary_roundtrip_max_abs": first_event["boundary_roundtrip_max_abs"],
                "trained_memory_preserved": True,
            },
            sort_keys=True,
        )
    )


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=12)
    parser.add_argument("--context-size", type=int, default=256)
    parser.add_argument("--coupling", type=float, default=DEFAULT_COUPLING)
    parser.add_argument("--commit-layer", type=int, default=32)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--model", type=Path, default=QWEN_MODEL_PATH)
    parser.add_argument("--dll-dir", type=Path, default=QWEN_DLL_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--self-check", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.self_check:
            _self_check(args.config, args.checkpoint)
            return 0
        receipt = _run(args)
        _write_receipt(args.receipt.resolve(), receipt)
        print(json.dumps({
            "verdict": receipt["verdict"],
            "receipt": str(args.receipt.resolve()),
            "zero_control_parity": receipt["comparison"]["zero_control_parity"],
            "initial_field_max_abs_logit_difference": receipt["comparison"]["initial_field_max_abs_logit_difference"],
            "first_token_divergence_index": receipt["comparison"]["first_token_divergence_index"],
            "baseline": receipt["baseline"]["output_utf8"],
            "field_control": receipt["field_control"]["output_utf8"],
        }, indent=2, ensure_ascii=False))
        return 0 if receipt["verdict"] == "PASS" else 1
    except (FieldControlError, OSError, RuntimeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
