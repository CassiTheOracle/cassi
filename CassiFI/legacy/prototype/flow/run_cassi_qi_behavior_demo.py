#!/usr/bin/env python3
"""Run a bounded, deterministic comparison of the canonical Qi field and KV memory.

The receipt deliberately contains only scalar telemetry, identities, hashes, byte
accounting, decisions, and a few retrieval rows.  It never serializes a field
array.  The runner is CPU-only and does not require llama.cpp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_qi_field import (
    QI_CODEBOOK_PROFILE_ID,
    QI_FIELD_CONFIG_SCHEMA,
    QI_FIELD_LAYOUT_ID,
    QI_FIELD_OPERATOR_PROFILE_ID,
    QI_FIELD_STATE_SCHEMA,
    QiFieldConfig,
    QiFieldController,
)
from cassi_qi_kv import (
    QI_KV_BINDING_PROFILE_ID,
    QI_KV_CONFIG_SCHEMA,
    QI_KV_STATE_SCHEMA,
    QiKVConfig,
    QiKVMemory,
    load_field_checkpoint,
    save_field_checkpoint,
)


_RECEIPT_SCHEMA = "cassi.qi.behavior-demo.v1"
_DEFAULT_EVENTS = 24
_DEFAULT_QUERIES = 8
_MAX_EVENTS = 4096
_MAX_QUERIES = 1024


def _safe_float(value: Any) -> float | None:
    """Convert a scalar to a JSON-safe finite float, or report unavailable."""

    try:
        result = float(value.item() if torch.is_tensor(value) else value)
    except (TypeError, ValueError, RuntimeError):
        return None
    return result if math.isfinite(result) else None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value.item() if torch.is_tensor(value) else value)
    except (TypeError, ValueError, RuntimeError):
        return None


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value.item() if torch.is_tensor(value) else value)
    except (TypeError, ValueError, RuntimeError):
        return False


def _finite_tensor(value: Any) -> bool:
    try:
        return bool(torch.isfinite(value).all().item())
    except (TypeError, ValueError, RuntimeError):
        return False


def _tensor_hash(value: torch.Tensor) -> str:
    """Hash a tensor without placing its contents in the receipt."""

    tensor = value.detach().cpu().contiguous()
    # A byte view avoids a NumPy dependency while preserving exact F32/F64 bits.
    raw = tensor.view(torch.uint8).numpy().tobytes()
    descriptor = f"{tensor.dtype}:{tuple(int(item) for item in tensor.shape)}:".encode("utf-8")
    return hashlib.sha256(descriptor + raw).hexdigest()



def _safe_vector(value: torch.Tensor) -> list[float | None]:
    result: list[float | None] = []
    for item in value.detach().cpu().flatten().tolist():
        result.append(_safe_float(item))
    return result


def _safe_max_abs(value: torch.Tensor) -> float | None:
    try:
        return _safe_float(value.detach().abs().max())
    except (TypeError, ValueError, RuntimeError):
        return None


def _safe_max_difference(left: torch.Tensor, right: torch.Tensor) -> float | None:
    try:
        return _safe_float((left.detach() - right.detach()).abs().max())
    except (TypeError, ValueError, RuntimeError):
        return None


def _safe_norm(value: torch.Tensor) -> float | None:
    try:
        return _safe_float(torch.linalg.vector_norm(value.detach()))
    except (TypeError, ValueError, RuntimeError):
        return None


def _mean(values: Sequence[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not finite:
        return None
    return sum(finite) / len(finite)


def _decision(passed: bool | None) -> str:
    if passed is True:
        return "PASS"
    if passed is False:
        return "FAIL"
    return "NEUTRAL"


def _comparison(name: str, decision: str, reason: str, **metrics: Any) -> dict[str, Any]:
    if decision not in {"PASS", "FAIL", "NEUTRAL"}:
        raise ValueError(f"invalid comparison decision: {decision}")
    result: dict[str, Any] = {"name": name, "decision": decision, "reason": reason}
    result.update(metrics)
    return result


def _anchor_check(
    name: str,
    observed: Mapping[str, float | None],
    expected: Mapping[str, float],
    tolerance: float,
) -> dict[str, Any]:
    errors: dict[str, float | None] = {}
    for key, target in expected.items():
        actual = observed.get(key)
        errors[key] = None if actual is None else abs(actual - target)
    finite_errors = [error for error in errors.values() if error is not None and math.isfinite(error)]
    passed = len(finite_errors) == len(expected) and all(error <= tolerance for error in finite_errors)
    return _comparison(
        name,
        _decision(passed),
        "analytic values agree within the declared tolerance" if passed else "measured analytic anchor differs or is unavailable",
        observed=dict(observed),
        expected=dict(expected),
        absolute_error=errors,
        tolerance=tolerance,
    )


def _field_budget(state: Any) -> dict[str, Any]:
    field = state.field
    return {
        "shape": [int(item) for item in field.shape],
        "elements": int(field.numel()),
        "bytes": int(field.numel() * field.element_size()),
        "dtype": str(field.dtype).replace("torch.", ""),
        "components_per_bank": 9,
    }


def _field_stats(state: Any, maximum: float) -> dict[str, Any]:
    field = state.field
    finite = _finite_tensor(field)
    observed_max = _safe_max_abs(field)
    bounded = observed_max is not None and observed_max <= maximum + 1.0e-9
    return {
        "finite": finite,
        "max_abs": observed_max,
        "bound": float(maximum),
        "bounded": bounded,
        "state_hash": _tensor_hash(field),
    }


def _field_readout_row(label: str, readout: Any) -> dict[str, Any]:
    symbols = readout.symbols.detach().cpu().flatten()
    symbol = _safe_int(symbols[0]) if symbols.numel() else None
    return {
        "label": label,
        "available": _safe_bool(readout.available.flatten()[0]) if readout.available.numel() else False,
        "symbol": symbol,
        "q": _safe_float(readout.q.flatten()[0]) if readout.q.numel() else None,
        "q_max": _safe_float(readout.q_max.flatten()[0]) if readout.q_max.numel() else None,
        "chi": _safe_float(readout.chi.flatten()[0]) if readout.chi.numel() else None,
        "cross_scale_coherence": _safe_float(readout.cross_scale_coherence.flatten()[0]) if readout.cross_scale_coherence.numel() else None,
        "read_gate": _safe_float(readout.read_gate.flatten()[0]) if readout.read_gate.numel() else None,
        "margin": _safe_float(readout.margin.flatten()[0]) if readout.margin.numel() else None,
        "uncertainty": _safe_float(readout.uncertainty.flatten()[0]) if readout.uncertainty.numel() else None,
    }


def _analytic_anchors() -> dict[str, Any]:
    """Measure the closed-form Qi anchors used by the reference tests."""

    config = QiFieldConfig(scale_count=1, mode_count=16, alphabet_size=8)
    controller = QiFieldController(config)
    phi = float(config.phi)

    equilibrium = controller.initial_state(1, dtype=torch.float64)
    equilibrium_packed = equilibrium.field.reshape(1, 9, config.mode_count, 1)
    equilibrium_packed[0, 0].fill_(1.0)
    equilibrium_packed[0, 2].fill_(phi**-0.5)
    equilibrium_metrics = controller.diagnostics(equilibrium)
    equilibrium_observed = {
        "rho": _safe_float(equilibrium_metrics.rho[0, 0]),
        "epsilon": _safe_float(equilibrium_metrics.epsilon[0, 0]),
        "q": _safe_float(equilibrium_metrics.q[0, 0]),
        "q_max": _safe_float(equilibrium_metrics.q_max[0, 0]),
        "chi": _safe_float(equilibrium_metrics.chi[0, 0]),
    }
    equilibrium_expected = {
        "rho": phi,
        "epsilon": 0.0,
        "q": phi**2 / (phi**2 + phi**-2),
        "q_max": phi**2 / (phi**2 + phi**-2),
        "chi": 1.0,
    }

    unit = controller.initial_state(1, dtype=torch.float64)
    unit.field.reshape(1, 9, config.mode_count, 1)[0, 0].fill_(1.0)
    unit_metrics = controller.diagnostics(unit)
    unit_observed = {
        "rho": _safe_float(unit_metrics.rho[0, 0]),
        "q": _safe_float(unit_metrics.q[0, 0]),
        "q_max": _safe_float(unit_metrics.q_max[0, 0]),
    }
    unit_expected = {
        "rho": 1.0,
        "q": 1.0 / (1.0 + phi**-2),
        "q_max": 1.0 / (1.0 + phi**-2),
    }

    iir_state = controller.initial_state(1, dtype=torch.float64)
    iir_packed = iir_state.field.reshape(1, 9, config.mode_count, 1)
    iir_packed[0, 0].fill_(phi)
    iir_packed[0, 2].fill_(1.0)
    iir_evolved = controller.evolve(iir_state, steps=1)
    iir_metrics = controller.diagnostics(iir_evolved)
    iir_observed = {
        "epsilon": _safe_float(iir_metrics.epsilon[0, 0]),
        "epsilon2_ema": _safe_float(iir_metrics.epsilon2_ema[0, 0]),
    }
    iir_expected = {"epsilon": 1.0, "epsilon2_ema": float(config.epsilon_tau)}

    kv_config = QiKVConfig(
        mode="replace",
        scale_count=1,
        head_count=1,
        mode_count=16,
        key_dim=4,
        value_dim=1,
        read_threshold=0.001,
    )
    kv_memory = QiKVMemory(kv_config)
    kv_state = kv_memory.initial_state(dtype=torch.float64)
    modes = kv_config.mode_count
    kv_state.field[0, :modes, 0] = 1.0
    kv_state.field[0, 2 * modes : 3 * modes, 0] = phi**-0.5
    kv_anchor = kv_memory.query(kv_state, 0, position=0)
    kv_expected_q = phi**2 / (phi**2 + phi**-2)
    kv_observed = {
        "q": _safe_float(kv_anchor.q),
        "q_max": _safe_float(kv_anchor.q_max),
        "chi": _safe_float(kv_anchor.chi),
        "read_gate": _safe_float(kv_anchor.read_gate),
    }
    kv_expected = {"q": kv_expected_q, "q_max": kv_expected_q, "chi": 1.0, "read_gate": 1.0}

    comparisons = [
        _anchor_check("field_equilibrium_anchor", equilibrium_observed, equilibrium_expected, 1.0e-9),
        _anchor_check("field_unit_anchor", unit_observed, unit_expected, 1.0e-9),
        _anchor_check("field_epsilon_iir_anchor", iir_observed, iir_expected, 1.0e-9),
        _anchor_check("kv_balanced_q_anchor", kv_observed, kv_expected, 1.0e-6),
    ]
    return {
        "identities": {
            "field_config_schema": QI_FIELD_CONFIG_SCHEMA,
            "field_state_schema": QI_FIELD_STATE_SCHEMA,
            "field_layout_id": QI_FIELD_LAYOUT_ID,
            "field_operator_profile_id": QI_FIELD_OPERATOR_PROFILE_ID,
            "field_codebook_profile_id": QI_CODEBOOK_PROFILE_ID,
            "field_config_fingerprint": controller.config_fingerprint,
            "field_codebook_fingerprint": controller.codebook_fingerprint,
            "kv_config_schema": QI_KV_CONFIG_SCHEMA,
            "kv_state_schema": QI_KV_STATE_SCHEMA,
            "kv_binding_profile_id": QI_KV_BINDING_PROFILE_ID,
            "kv_config_fingerprint": kv_memory.config_fingerprint,
            "kv_codebook_fingerprint": kv_memory.codebook_fingerprint,
        },
        "receipts": {
            "field_equilibrium": {"observed": equilibrium_observed, "expected": equilibrium_expected},
            "field_unit": {"observed": unit_observed, "expected": unit_expected},
            "field_epsilon_iir": {"observed": iir_observed, "expected": iir_expected},
            "kv_balanced": {"observed": kv_observed, "expected": kv_expected},
        },
        "comparisons": comparisons,
    }


def _field_stream(seed: int, event_count: int) -> dict[str, Any]:
    """Compare one scale with consensus while keeping adaptive field elements equal."""

    alphabet_size = 8
    control_config = QiFieldConfig(scale_count=1, mode_count=32, alphabet_size=alphabet_size)
    multi_config = QiFieldConfig(scale_count=2, mode_count=16, alphabet_size=alphabet_size)
    control = QiFieldController(control_config)
    multi = QiFieldController(multi_config)
    control_state = control.initial_state(1, dtype=torch.float64)
    multi_state = multi.initial_state(1, dtype=torch.float64)
    control_codes = control.codebooks(dtype=torch.float64)
    multi_codes = multi.codebooks(dtype=torch.float64)

    rng = random.Random((int(seed) << 1) ^ 0x51F71E1D)
    repeated_symbols = [rng.randrange(alphabet_size) for _ in range((event_count + 1) // 2)]
    rows: list[dict[str, Any]] = []
    control_interference_rows: list[dict[str, Any]] = []
    multi_interference_rows: list[dict[str, Any]] = []

    for index in range(event_count):
        symbol = repeated_symbols[index // 2]
        interference = bool(index % 2)
        sign = -1.0 if interference else 1.0
        control_wave = (sign * control_codes[0, symbol]).unsqueeze(0)
        multi_wave = (sign * multi_codes[0, symbol]).unsqueeze(0)
        control_state = control.sense_wave(control_state, control_wave)
        multi_state = multi.sense_wave(multi_state, multi_wave)
        # A normal write is also offered to the slower bank.  On an inverted
        # event, its phase gate can reject the transfer, leaving consensus to
        # compare the fast inverted bank with the retained slow bank.
        multi_state = multi.consolidate(multi_state)
        control_readout = control.emit(control_state)
        multi_readout = multi.emit(multi_state)
        control_row = _field_readout_row("single_scale", control_readout)
        multi_row = _field_readout_row("multi_scale", multi_readout)
        event_row = {
            "event": index,
            "symbol": symbol,
            "interference": interference,
            "single_scale": control_row,
            "multi_scale": multi_row,
        }
        rows.append(event_row)
        if interference:
            control_interference_rows.append(control_row)
            multi_interference_rows.append(multi_row)

    control_budget = _field_budget(control_state)
    multi_budget = _field_budget(multi_state)
    matched = (
        control_budget["elements"] == multi_budget["elements"]
        and control_budget["bytes"] == multi_budget["bytes"]
    )
    budget_comparison = _comparison(
        "matched_adaptive_state_budget",
        _decision(matched),
        "single-scale and multiscale field tensors have equal element and byte budgets" if matched else "adaptive-state budgets differ",
        control=control_budget,
        multi_scale=multi_budget,
    )

    control_available = sum(1 for row in control_interference_rows if row["available"])
    multi_available = sum(1 for row in multi_interference_rows if row["available"])
    control_gates = [row["read_gate"] for row in control_interference_rows]
    multi_gates = [row["read_gate"] for row in multi_interference_rows]
    control_gate_mean = _mean(control_gates)
    multi_gate_mean = _mean(multi_gates)
    interference_count = len(control_interference_rows)
    if interference_count == 0:
        interference_decision = "NEUTRAL"
        interference_reason = "no interference events were requested"
    elif control_gate_mean is None or multi_gate_mean is None:
        interference_decision = "FAIL"
        interference_reason = "one or both read-gate measurements were unavailable"
    elif multi_available < control_available and multi_gate_mean <= control_gate_mean + 1.0e-12:
        interference_decision = "PASS"
        interference_reason = "multiscale consensus emitted fewer inverted events with no higher mean gate"
    elif multi_available > control_available or multi_gate_mean > control_gate_mean + 1.0e-12:
        interference_decision = "FAIL"
        interference_reason = "multiscale consensus did not suppress the measured inverted events"
    else:
        interference_decision = "NEUTRAL"
        interference_reason = "measured availability and gate outcomes were tied"
    interference_comparison = _comparison(
        "multiscale_interference_suppression",
        interference_decision,
        interference_reason,
        interference_events=interference_count,
        single_scale_available=control_available,
        multi_scale_available=multi_available,
        single_scale_mean_read_gate=control_gate_mean,
        multi_scale_mean_read_gate=multi_gate_mean,
    )

    control_stats = _field_stats(control_state, control_config.physics.max_mode_amplitude)
    multi_stats = _field_stats(multi_state, multi_config.physics.max_mode_amplitude)
    finite_bounded = bool(control_stats["finite"] and control_stats["bounded"] and multi_stats["finite"] and multi_stats["bounded"])
    bounded_comparison = _comparison(
        "field_stream_finite_and_bounded",
        _decision(finite_bounded),
        "both measured field states remained finite and within configured amplitude bounds" if finite_bounded else "a measured stream field was non-finite or exceeded its configured bound",
        single_scale=control_stats,
        multi_scale=multi_stats,
    )

    if len(rows) <= 6:
        representative = rows
    else:
        representative = rows[:4] + rows[-2:]
    return {
        "protocol": {
            "control": "single_scale_no_consensus",
            "canonical": QI_FIELD_OPERATOR_PROFILE_ID,
            "event_stream": "seeded_repeated_symbol_pairs_with_inverted_second_event",
            "seed_derivation": "random.Random((seed << 1) ^ 0x51F71E1D)",
        },
        "events_requested": int(event_count),
        "events_executed": len(rows),
        "interference_events": interference_count,
        "control_identity": {
            "config_fingerprint": control.config_fingerprint,
            "codebook_fingerprint": control.codebook_fingerprint,
        },
        "multi_scale_identity": {
            "config_fingerprint": multi.config_fingerprint,
            "codebook_fingerprint": multi.codebook_fingerprint,
        },
        "matched_budget": matched,
        "comparisons": [budget_comparison, interference_comparison, bounded_comparison],
        "representative_events": representative,
        "terminal": {
            "single_scale": control_stats,
            "multi_scale": multi_stats,
        },
    }


def _kv_config(mode: str, *, scale_count: int = 1, local_window: int = 3) -> QiKVConfig:
    return QiKVConfig(
        mode=mode,
        scale_count=scale_count,
        head_count=1,
        mode_count=32,
        key_dim=4,
        value_dim=2,
        local_window=local_window,
        read_threshold=0.01,
    )


def _kv_row(label: str, result: Any) -> dict[str, Any]:
    return {
        "label": label,
        "available": bool(result.available),
        "exact": bool(result.exact),
        "local_available": bool(result.local_available),
        "field_available": bool(result.field_available),
        "q": _safe_float(result.q),
        "q_max": _safe_float(result.q_max),
        "epsilon2_ema": _safe_float(result.epsilon2_ema),
        "chi": _safe_float(result.chi),
        "cross_scale_coherence": _safe_float(result.cross_scale_coherence),
        "read_gate": _safe_float(result.read_gate),
        "local_weight": _safe_float(result.local_weight),
        "field_weight": _safe_float(result.field_weight),
        "value": _safe_vector(result.value),
        "value_l2": _safe_norm(result.value),
        "memory_bytes": result.memory_bytes.as_dict(),
    }


def _value_error(result: Any, expected: Sequence[float]) -> float | None:
    try:
        target = torch.as_tensor(expected, device=result.value.device, dtype=result.value.dtype)
        return _safe_float((result.value - target).abs().max())
    except (TypeError, ValueError, RuntimeError):
        return None


def _kv_stats(memory: QiKVMemory, state: Any) -> dict[str, Any]:
    return {
        "finite": _finite_tensor(state.field),
        "max_abs": _safe_max_abs(state.field),
        "bound": float(memory.config.max_field_norm),
        "bounded": (_safe_max_abs(state.field) is not None and _safe_max_abs(state.field) <= memory.config.max_field_norm + 1.0e-9),
        "state_hash": _tensor_hash(state.field),
    }


def _associative_kv(seed: int, query_count: int) -> dict[str, Any]:
    del seed  # The fixed keys and values make each behavior receipt comparable.
    exact_config = _kv_config("compress", scale_count=2, local_window=3)
    exact_memory = QiKVMemory(exact_config)
    exact_state = exact_memory.initial_state(dtype=torch.float64)
    exact_value = [1.0, -0.5]
    exact_state = exact_memory.deposit(exact_state, 11.0, exact_value, position=0)
    exact_result = exact_memory.query(exact_state, 11.0, position=1)
    exact_error = _value_error(exact_result, exact_value)
    exact_pass = bool(exact_result.available and exact_result.exact and exact_result.local_available and exact_error is not None and exact_error <= 1.0e-12)
    exact_comparison = _comparison(
        "kv_exact_local",
        _decision(exact_pass),
        "the bounded exact ring returned the matching recent value" if exact_pass else "the recent exact-local value was not returned exactly",
        value_error=exact_error,
    )

    assist_config = _kv_config("assist", scale_count=1)
    assist_memory = QiKVMemory(assist_config)
    assist_empty = assist_memory.initial_state(dtype=torch.float64)
    external_value = [4.0, 5.0]
    fallback_result = assist_memory.query(
        assist_empty,
        3.0,
        position=0,
        external_full={"value": external_value, "weight": 0.75},
    )
    fallback_error = _value_error(fallback_result, external_value)
    fallback_pass = bool(
        fallback_result.available
        and fallback_result.local_available
        and not fallback_result.field_available
        and fallback_result.field_weight == 0.0
        and fallback_error is not None
        and fallback_error <= 1.0e-12
    )
    fallback_comparison = _comparison(
        "kv_unavailable_field_fallback",
        _decision(fallback_pass),
        "assist mode used the external candidate while the Qi field was unavailable" if fallback_pass else "assist fallback did not preserve the available external candidate",
        value_error=fallback_error,
    )

    assist_value = [0.75, -1.25]
    assist_state = assist_memory.deposit(assist_empty, 3.0, assist_value, position=0)
    assist_result = assist_memory.query(
        assist_state,
        3.0,
        position=0,
        external_full={"value": external_value, "weight": 0.75},
    )
    assist_base_ok = bool(assist_result.available and assist_result.local_available and abs(float(assist_result.local_weight) - 0.75) <= 1.0e-12)
    if assist_base_ok and assist_result.field_available and float(assist_result.field_weight) > 0.0:
        assist_decision = "PASS"
        assist_reason = "assist mode combined an external candidate with a gated field contribution"
    elif assist_base_ok:
        assist_decision = "NEUTRAL"
        assist_reason = "external assist candidate was available but the measured field gate abstained"
    else:
        assist_decision = "FAIL"
        assist_reason = "assist mode did not return the external candidate contract"
    assist_comparison = _comparison(
        "kv_field_assist",
        assist_decision,
        assist_reason,
        expected_external_weight=0.75,
    )

    compress_config = _kv_config("compress", scale_count=1, local_window=2)
    compress_memory = QiKVMemory(compress_config)
    compress_state = compress_memory.initial_state(dtype=torch.float64)
    compress_state = compress_memory.deposit(compress_state, 1.0, [1.0, 0.0], position=0)
    for position in range(1, 7):
        compress_state = compress_memory.deposit(
            compress_state,
            float(position + 20),
            [float(position) * 0.25, -float(position) * 0.125],
            position=position,
        )
    compress_result = compress_memory.query(compress_state, 1.0, position=12)
    compress_ok = bool(compress_result.available and compress_result.field_available and not compress_result.exact and not compress_result.local_available)
    compress_comparison = _comparison(
        "kv_compress_evicted_local_field_read",
        _decision(compress_ok),
        "after local-ring eviction, the field supplied a finite non-local result" if compress_ok else "the evicted compress query did not produce the expected field-only result",
    )

    replace_config = _kv_config("replace", scale_count=1)
    replace_memory = QiKVMemory(replace_config)
    replace_empty = replace_memory.initial_state(dtype=torch.float64)
    replace_unavailable = replace_memory.query(
        replace_empty,
        5.0,
        position=0,
        external_full=[9.0, 9.0],
        external_local=[8.0, 8.0],
    )
    replace_unavailable_pass = bool(not replace_unavailable.available and replace_unavailable.zero and not replace_unavailable.field_available)
    replace_unavailable_comparison = _comparison(
        "kv_replace_unavailable_field_abstention",
        _decision(replace_unavailable_pass),
        "replace mode abstained with a zero result when no field signal was present" if replace_unavailable_pass else "replace mode returned an unexpected external or nonzero result without a field signal",
    )
    replace_value = [0.5, 1.25]
    replace_state = replace_memory.deposit(replace_empty, 5.0, replace_value, position=0)
    replace_result = replace_memory.query(replace_state, 5.0, position=0)
    replace_pass = bool(replace_result.available and replace_result.field_available and not replace_result.exact)
    replace_comparison = _comparison(
        "kv_replace_field_read",
        _decision(replace_pass),
        "replace mode returned the field-owned result without an exact local ring" if replace_pass else "replace mode did not return a field-owned result after deposit",
    )

    probe_rows: list[dict[str, Any]] = []
    probe_results: list[Any] = []
    for index in range(query_count):
        if index % 3 == 0:
            result = compress_memory.query(compress_state, 1.0, position=20 + index)
            label = f"probe_compress_{index}"
        elif index % 3 == 1:
            result = assist_memory.query(
                assist_state,
                3.0,
                position=1 + index,
                external_full={"value": external_value, "weight": 0.75},
            )
            label = f"probe_assist_{index}"
        else:
            result = replace_memory.query(replace_state, 5.0, position=index)
            label = f"probe_replace_{index}"
        probe_results.append(result)
        if len(probe_rows) < 4:
            probe_rows.append(_kv_row(label, result))

    all_states = [exact_state, assist_state, compress_state, replace_state]
    all_memories = [exact_memory, assist_memory, compress_memory, replace_memory]
    state_stats = [_kv_stats(memory, state) for memory, state in zip(all_memories, all_states)]
    compress_budget = compress_memory.memory_bytes(compress_state)
    full_kv_entry_bytes = int(compress_budget.local_entry_bytes)
    matched_full_entries = int(compress_budget.total_bytes // full_kv_entry_bytes)
    matched_full_bytes = int(matched_full_entries * full_kv_entry_bytes)
    unused_matched_bytes = int(compress_budget.total_bytes - matched_full_bytes)
    budget_accounting_ok = bool(
        full_kv_entry_bytes > 0
        and matched_full_bytes <= compress_budget.total_bytes
        and 0 <= unused_matched_bytes < full_kv_entry_bytes
    )
    budget_comparison = _comparison(
        "kv_matched_memory_budget_accounting",
        _decision(budget_accounting_ok),
        "the Qi allocation and standard full-KV reference use the same declared byte ceiling"
        if budget_accounting_ok
        else "matched standard full-KV capacity could not be computed from the declared byte budget",
        qi_total_bytes=int(compress_budget.total_bytes),
        full_kv_entry_bytes=full_kv_entry_bytes,
        matched_full_kv_entries=matched_full_entries,
        matched_full_kv_bytes=matched_full_bytes,
        unused_bytes=unused_matched_bytes,
        head_count=int(compress_config.head_count),
        layer_count=1,
    )
    all_bounded = all(bool(item["finite"] and item["bounded"]) for item in state_stats)
    bounded_comparison = _comparison(
        "kv_field_finite_and_bounded",
        _decision(all_bounded),
        "all associative-memory field states remained finite and within max_field_norm" if all_bounded else "an associative-memory field state was non-finite or exceeded max_field_norm",
        states=state_stats,
    )

    comparisons = [
        exact_comparison,
        fallback_comparison,
        assist_comparison,
        compress_comparison,
        replace_unavailable_comparison,
        replace_comparison,
        bounded_comparison,
        budget_comparison,
    ]
    rows = [
        _kv_row("exact_local", exact_result),
        _kv_row("assist_unavailable_field_fallback", fallback_result),
        _kv_row("field_assist", assist_result),
        _kv_row("compress_after_local_eviction", compress_result),
        _kv_row("replace_empty_external_ignored", replace_unavailable),
        _kv_row("replace_field", replace_result),
    ]
    return {
        "identities": {
            "exact_compress": {"config_fingerprint": exact_memory.config_fingerprint, "codebook_fingerprint": exact_memory.codebook_fingerprint},
            "assist": {"config_fingerprint": assist_memory.config_fingerprint, "codebook_fingerprint": assist_memory.codebook_fingerprint},
            "compress": {"config_fingerprint": compress_memory.config_fingerprint, "codebook_fingerprint": compress_memory.codebook_fingerprint},
            "replace": {"config_fingerprint": replace_memory.config_fingerprint, "codebook_fingerprint": replace_memory.codebook_fingerprint},
        },
        "memory_bytes": {
            "exact_compress": exact_memory.memory_bytes(exact_state).as_dict(),
            "assist": assist_memory.memory_bytes(assist_state).as_dict(),
            "compress": compress_memory.memory_bytes(compress_state).as_dict(),
            "replace": replace_memory.memory_bytes(replace_state).as_dict(),
        },
        "matched_standard_full_kv_budget": {
            "qi_total_bytes": int(compress_budget.total_bytes),
            "bytes_per_head_layer": int(compress_budget.total_bytes),
            "full_kv_entry_bytes": full_kv_entry_bytes,
            "matched_full_kv_entries": matched_full_entries,
            "matched_full_kv_bytes": matched_full_bytes,
            "unused_bytes": unused_matched_bytes,
            "head_count": int(compress_config.head_count),
            "layer_count": 1,
        },
        "queries_requested": int(query_count),
        "additional_probe_queries_executed": len(probe_results),
        "comparisons": comparisons,
        "representative_retrieval_rows": rows,
        "representative_probe_rows": probe_rows,
    }


def _continuation() -> dict[str, Any]:
    """Round-trip exact field-only artifacts and compare the same continuation."""

    field_config = QiFieldConfig(scale_count=2, mode_count=16, alphabet_size=8)
    field_controller = QiFieldController(field_config)
    field_state = field_controller.initial_state(1, dtype=torch.float64)
    for symbol in (2, 5):
        field_state = field_controller.sense_symbols(field_state, [symbol])
        field_state = field_controller.evolve(field_state, steps=1)
        field_state = field_controller.consolidate(field_state)
    field_before_hash = _tensor_hash(field_state.field)
    with tempfile.TemporaryDirectory(prefix="cassi-qi-behavior-") as directory:
        field_path = Path(directory) / "qi-field.pt"
        field_digest = field_controller.save(field_path, field_state)
        loaded_field = field_controller.load(field_path, dtype=torch.float64)
        continued_original = field_controller.cycle(field_state, current_symbols=[3], learn=False).state
        continued_loaded = field_controller.cycle(loaded_field, current_symbols=[3], learn=False).state
        field_diff = _safe_max_difference(continued_original.field, continued_loaded.field)
        field_file_bytes = int(field_path.stat().st_size)
    field_stats = _field_stats(field_state, field_config.physics.max_mode_amplitude)
    field_identity = bool(
        _tensor_hash(loaded_field.field) == field_before_hash
        and field_diff is not None
        and field_diff <= 0.0
        and len(field_digest) == 64
        and bool(field_stats["finite"] and field_stats["bounded"])
    )
    field_comparison = _comparison(
        "field_checkpoint_continuation_identity",
        _decision(field_identity),
        "load restored the exact field and produced an identical deterministic continuation" if field_identity else "field checkpoint or continuation identity differed",
        checkpoint_sha256=field_digest,
        checkpoint_bytes=field_file_bytes,
        state_hash_before=field_before_hash,
        state_hash_after_continuation=_tensor_hash(continued_original.field),
        continuation_max_abs_difference=field_diff,
    )

    kv_config = QiKVConfig(
        mode="replace",
        scale_count=2,
        head_count=1,
        mode_count=16,
        key_dim=4,
        value_dim=2,
        read_threshold=0.01,
    )
    kv_memory = QiKVMemory(kv_config)
    kv_state = kv_memory.initial_state(dtype=torch.float64)
    kv_state = kv_memory.deposit(kv_state, 17.0, [0.5, -0.25], position=0)
    kv_before_hash = _tensor_hash(kv_state.field)
    with tempfile.TemporaryDirectory(prefix="cassi-qi-kv-behavior-") as directory:
        kv_path = Path(directory) / "qi-kv-field.pt"
        kv_digest = save_field_checkpoint(kv_path, kv_memory, kv_state)
        loaded_kv = load_field_checkpoint(kv_path, kv_memory, dtype=torch.float64)
        continued_kv_original = kv_memory.deposit(kv_state, 19.0, [0.25, 0.75], position=1)
        continued_kv_loaded = kv_memory.deposit(loaded_kv, 19.0, [0.25, 0.75], position=1)
        kv_diff = _safe_max_difference(continued_kv_original.field, continued_kv_loaded.field)
        kv_file_bytes = int(kv_path.stat().st_size)
    kv_stats = _kv_stats(kv_memory, kv_state)
    kv_identity = bool(
        _tensor_hash(loaded_kv.field) == kv_before_hash
        and kv_diff is not None
        and kv_diff <= 0.0
        and len(kv_digest) == 64
        and bool(kv_stats["finite"] and kv_stats["bounded"])
    )
    kv_comparison = _comparison(
        "kv_checkpoint_continuation_identity",
        _decision(kv_identity),
        "load restored the exact canonical field and produced an identical deterministic continuation" if kv_identity else "KV field checkpoint or continuation identity differed",
        checkpoint_sha256=kv_digest,
        checkpoint_bytes=kv_file_bytes,
        state_hash_before=kv_before_hash,
        state_hash_after_continuation=_tensor_hash(continued_kv_original.field),
        continuation_max_abs_difference=kv_diff,
    )
    bounded_comparison = _comparison(
        "checkpoint_states_finite_and_bounded",
        _decision(bool(field_stats["finite"] and field_stats["bounded"] and kv_stats["finite"] and kv_stats["bounded"])),
        "checkpoint source states were finite and bounded" if bool(field_stats["finite"] and field_stats["bounded"] and kv_stats["finite"] and kv_stats["bounded"]) else "a checkpoint source state was non-finite or out of bounds",
        field=field_stats,
        kv=kv_stats,
    )
    return {
        "field": {
            "config_fingerprint": field_controller.config_fingerprint,
            "codebook_fingerprint": field_controller.codebook_fingerprint,
            "checkpoint_sha256": field_digest,
            "checkpoint_bytes": field_file_bytes,
            "state_hash_before": field_before_hash,
            "continuation_max_abs_difference": field_diff,
        },
        "kv": {
            "config_fingerprint": kv_memory.config_fingerprint,
            "codebook_fingerprint": kv_memory.codebook_fingerprint,
            "checkpoint_sha256": kv_digest,
            "checkpoint_bytes": kv_file_bytes,
            "state_hash_before": kv_before_hash,
            "continuation_max_abs_difference": kv_diff,
        },
        "comparisons": [field_comparison, kv_comparison, bounded_comparison],
    }


def _all_comparisons(*sections: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in sections:
        values = section.get("comparisons", ())
        if isinstance(values, Sequence):
            result.extend(item for item in values if isinstance(item, dict))
    return result


def _overall_status(comparisons: Sequence[Mapping[str, Any]]) -> str:
    decisions = [str(item.get("decision")) for item in comparisons]
    if "FAIL" in decisions:
        return "FAIL"
    if decisions and all(decision == "NEUTRAL" for decision in decisions):
        return "NEUTRAL"
    return "PASS"


def _assert_finite_json(value: Any, path: str = "receipt") -> None:
    """Reject accidental NaN/Infinity and non-JSON values before writing."""

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite JSON value at {path}")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string JSON key at {path}")
            _assert_finite_json(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_finite_json(item, f"{path}[{index}]")
    elif isinstance(value, (str, int, bool)) or value is None:
        return
    else:
        raise ValueError(f"non-JSON value {type(value).__name__} at {path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic CPU-only Qi engineering demo: analytic anchors, "
            "matched-budget single-scale versus multiscale interference, associative "
            "KV retrieval modes, and checkpoint continuation identity."
        )
    )
    parser.add_argument("--seed", type=int, default=20260823, help="integer seed for the repeated-symbol event stream (default: %(default)s)")
    parser.add_argument(
        "--events",
        type=int,
        default=_DEFAULT_EVENTS,
        help=f"number of bounded repeated-symbol/interference events, 0..{_MAX_EVENTS} (default: %(default)s)",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=_DEFAULT_QUERIES,
        help=f"number of additional bounded associative retrieval probes, 0..{_MAX_QUERIES} (default: %(default)s)",
    )
    parser.add_argument("--output", "-o", type=Path, required=True, help="caller-provided JSON receipt path")
    return parser


def _validate_count(parser: argparse.ArgumentParser, name: str, value: int, maximum: int) -> None:
    if value < 0 or value > maximum:
        parser.error(f"--{name} must be an integer in [0, {maximum}]")


def run_demo(seed: int, event_count: int, query_count: int) -> dict[str, Any]:
    # All operations in the reference are analytic, but setting both generators
    # makes the seed contract explicit and protects future deterministic probes.
    random.seed(seed)
    torch.manual_seed(seed)
    anchors = _analytic_anchors()
    stream = _field_stream(seed, event_count)
    kv = _associative_kv(seed, query_count)
    continuation = _continuation()
    comparisons = _all_comparisons(anchors, stream, kv, continuation)
    status = _overall_status(comparisons)
    return {
        "schema": _RECEIPT_SCHEMA,
        "version": 1,
        "runtime": {"device": "cpu", "llama_cpp": False, "torch_dtype": "float64", "deterministic_seed": int(seed)},
        "seed": int(seed),
        "events_requested": int(event_count),
        "queries_requested": int(query_count),
        "status": status,
        "decision": status,
        "comparisons": comparisons,
        "analytic_anchors": anchors,
        "matched_budget_stream": stream,
        "associative_kv": kv,
        "checkpoint_continuation": continuation,
    }


def _write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    _assert_finite_json(receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_count(parser, "events", args.events, _MAX_EVENTS)
    _validate_count(parser, "queries", args.queries, _MAX_QUERIES)
    try:
        receipt = run_demo(args.seed, args.events, args.queries)
        _write_receipt(args.output, receipt)
    except Exception as exc:  # Keep failures finite and machine-readable.
        failure = {
            "schema": _RECEIPT_SCHEMA,
            "version": 1,
            "status": "FAIL",
            "decision": "FAIL",
            "seed": int(args.seed),
            "events_requested": int(args.events),
            "queries_requested": int(args.queries),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _write_receipt(args.output, failure)
        return 1
    return 0 if receipt.get("status") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
