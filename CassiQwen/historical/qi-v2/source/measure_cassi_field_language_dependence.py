"""Measure whether the canonical Qi field changes committed language symbols.

All three arms start from the same prompt-conditioned decision state and run an
identical field-native emit loop; they differ only in the state handed to that
loop.  ``qi_zeroed`` replaces the conditioned field with zeros (the whole state
is the qi sector, so this is the faithful "remove the field energy"
counterfactual).  ``scale_phase`` applies a deterministic phase rotation to the
Yang plane of scale 0 -- a purely field-native perturbation of the scale/phase
coordinates, touching no feature vector or logit.

The emit loop is driven only by ``QiFieldController.emit`` and
``QiFieldController.qi_state_sha256``.  There is no language head, no feature
extraction, no logits, no sampling configuration, no organism, and no trained
checkpoint.  A null decision result is a valid measurement and is never promoted
to a causal-effect claim.

The verdict changes only when a counterfactual changes the committed symbols or
the abstention status; otherwise the honest ``NULL_NO_SYMBOL_OR_ABSTENTION_CHANGE``
verdict is returned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import torch

from cassi_field_language import CassiFieldTextCodec, qi_state_sha256
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState


SCHEMA: Final[str] = "cassi.qi-field-dependence.v1"
MODEL_ID: Final[str] = "cassi-qi-language-v1"
_DEFAULT_MESSAGES: Final[tuple[dict[str, str], ...]] = (
    {"role": "user", "content": "Cassi field state counterfactual."},
)
_SCALE_PHASE_ANGLE: Final[float] = 1.0  # radians; a non-identity phase rotation


class CassiFieldDependenceError(RuntimeError):
    """A counterfactual artifact or field-language arm is invalid."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CassiFieldDependenceError(f"value is not canonical finite JSON: {error}") from error


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_mapping(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CassiFieldDependenceError(f"could not load {label}: {error}") from error
    if not isinstance(value, Mapping):
        raise CassiFieldDependenceError(f"{label} must be a JSON object")
    return value


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _decode_output_bytes(raw: bytes) -> tuple[str, bool, int]:
    try:
        return raw.decode("utf-8", "strict"), True, 0
    except UnicodeDecodeError:
        text = raw.decode("utf-8", "replace")
        return text, False, text.count("�")


def _condition_prompt(
    controller: QiFieldController,
    codec: CassiFieldTextCodec,
    initial_state: QiFieldState,
    messages: Sequence[Mapping[str, object]],
) -> QiFieldState:
    """Sense each prompt symbol through the fixed field, returning the decision state."""
    state = QiFieldState(initial_state.field.clone())
    for symbol in codec.encode_messages(messages):
        sensed = controller.sense_symbols(state, [symbol])
        evolved = controller.evolve(sensed)
        state = controller.consolidate(evolved)
    return state


def _qi_zeroed(state: QiFieldState) -> QiFieldState:
    """Remove all field energy: the faithful "no field" counterfactual."""
    return QiFieldState(torch.zeros_like(state.field))


def _perturb_scale_phase(state: QiFieldState, controller: QiFieldController) -> QiFieldState:
    """Rotate the Yang real/imaginary plane of scale 0 by a fixed phase.

    This is a purely field-native perturbation of the scale/phase coordinates:
    it preserves magnitude (so all amplitude/energy bounds remain satisfied) and
    touches no feature vector or logit.
    """
    field = state.field.clone()
    mode_count = controller.config.mode_count
    cos_t = math.cos(_SCALE_PHASE_ANGLE)
    sin_t = math.sin(_SCALE_PHASE_ANGLE)
    # Plane layout per scale is [Y_re, Y_im, I_re, I_im, VY_re, VY_im, VI_re, VI_im, epsilon2_ema];
    # in the packed [S, 9M, B] tensor, scale 0 plane p occupies [0, p*M:(p+1)*M, :].
    y_re = field[0, 0:mode_count, :].clone()
    y_im = field[0, mode_count : 2 * mode_count, :].clone()
    field[0, 0:mode_count, :] = cos_t * y_re - sin_t * y_im
    field[0, mode_count : 2 * mode_count, :] = sin_t * y_re + cos_t * y_im
    result = QiFieldState(field)
    result.validate(controller.config)
    return result


def _emit_arm(
    *,
    controller: QiFieldController,
    codec: CassiFieldTextCodec,
    start_state: QiFieldState,
    max_output_symbols: int,
) -> tuple[dict[str, Any], tuple[int, ...]]:
    """Run the deterministic field emit loop from a given decision state.

    Returns the per-arm receipt and the committed output symbols.  The receipt
    commits only emission diagnostics (symbol + before/after state hashes +
    flux/margin/uncertainty); there are no feature vectors or logits.
    """
    state = start_state
    initial_sha = qi_state_sha256(controller, state)
    output_symbols: list[int] = []
    output_bytes = bytearray()
    chain: list[dict[str, Any]] = []
    stop_reason = "max_output_symbols"
    for position in range(max_output_symbols):
        readout = controller.emit(state)
        available = bool(readout.available.reshape(-1)[0].item())
        if not available:
            stop_reason = "field_abstained"
            chain.append(
                {
                    "position": position,
                    "available": False,
                    "state_before_sha256": qi_state_sha256(controller, state),
                    "symbol": -1,
                }
            )
            break
        symbol = int(readout.symbols.reshape(-1)[0].item())
        sensed = controller.sense_symbols(state, [symbol])
        evolved = controller.evolve(sensed)
        successor = controller.consolidate(evolved)
        chain.append(
            {
                "position": position,
                "available": True,
                "symbol": symbol,
                "state_before_sha256": qi_state_sha256(controller, state),
                "state_after_sha256": qi_state_sha256(controller, successor),
                "flux": float(readout.flux.reshape(-1)[0].item()),
                "margin": float(readout.margin.reshape(-1)[0].item()),
                "uncertainty": float(readout.uncertainty.reshape(-1)[0].item()),
            }
        )
        state = successor
        output_symbols.append(symbol)
        if symbol == codec.end_turn_symbol:
            stop_reason = "end_turn"
            break
        if not 0 <= symbol < 256:
            stop_reason = "role_boundary"
            break
        output_bytes.append(symbol)

    raw = bytes(output_bytes)
    text, utf8_valid, replacement_count = _decode_output_bytes(raw)
    final_sha = qi_state_sha256(controller, state)
    abstained = stop_reason == "field_abstained"
    receipt = {
        "initial_state_sha256": initial_sha,
        "final_state_sha256": final_sha,
        "stop_reason": stop_reason,
        "abstained": abstained,
        "output_symbols": output_symbols,
        "output_symbols_sha256": _sha256(_canonical(output_symbols)),
        "output_bytes_sha256": _sha256(raw),
        "text_sha256": _sha256(text.encode("utf-8", "strict")),
        "utf8_valid": utf8_valid,
        "replacement_count": replacement_count,
        "committed_output_count": len(output_symbols),
        "receipt_chain_sha256": _sha256(_canonical(chain)),
        "all_outputs_field_owned": True,
    }
    return receipt, tuple(output_symbols)


def _first_changed_position(left: tuple[int, ...], right: tuple[int, ...]) -> int | None:
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def measure_qi_field_dependence(
    *,
    qi_config_path: Path,
    output: Path,
    max_output_symbols: int = 16,
    messages: Sequence[Mapping[str, object]] = _DEFAULT_MESSAGES,
) -> dict[str, Any]:
    if isinstance(max_output_symbols, bool) or not 1 <= max_output_symbols <= 256:
        raise CassiFieldDependenceError("max_output_symbols must lie in [1, 256]")
    if not messages:
        raise CassiFieldDependenceError("counterfactual messages cannot be empty")

    qi_config = QiFieldConfig.from_dict(_load_mapping(qi_config_path, "qi config"))
    controller = QiFieldController(qi_config)
    codec = CassiFieldTextCodec()

    initial_state = controller.initial_state(1, device="cpu", dtype=torch.float32)
    conditioned = _condition_prompt(controller, codec, initial_state, messages)

    variants: dict[str, QiFieldState] = {
        "live": conditioned,
        "qi_zeroed": _qi_zeroed(conditioned),
        "scale_phase": _perturb_scale_phase(conditioned, controller),
    }

    arm_by_name: dict[str, dict[str, Any]] = {}
    outputs: dict[str, tuple[int, ...]] = {}
    for name, state in variants.items():
        arm, symbols = _emit_arm(
            controller=controller,
            codec=codec,
            start_state=state,
            max_output_symbols=max_output_symbols,
        )
        arm["name"] = name
        arm_by_name[name] = arm
        outputs[name] = symbols

    # Every counterfactual must actually change the prompt-conditioned decision
    # state; otherwise it is not a counterfactual at all.
    live_init = arm_by_name["live"]["initial_state_sha256"]
    for name in ("qi_zeroed", "scale_phase"):
        if arm_by_name[name]["initial_state_sha256"] == live_init:
            raise CassiFieldDependenceError(
                f"{name} counterfactual did not change the prompt-conditioned decision state"
            )

    live_symbols = outputs["live"]
    comparisons: dict[str, dict[str, Any]] = {}
    for name, symbols in outputs.items():
        if name == "live":
            continue
        other = arm_by_name[name]
        live = arm_by_name["live"]
        decision_changed = symbols != live_symbols
        abstention_changed = other["abstained"] != live["abstained"]
        comparisons[name] = {
            "initial_state_changed": other["initial_state_sha256"] != live_init,
            "decision_changed": decision_changed,
            "abstention_changed": abstention_changed,
            "first_changed_position": _first_changed_position(live_symbols, symbols),
            "output_symbols_changed": decision_changed,
            "output_bytes_changed": other["output_bytes_sha256"] != live["output_bytes_sha256"],
            "stop_reason_changed": other["stop_reason"] != live["stop_reason"],
            "final_state_changed": other["final_state_sha256"] != live["final_state_sha256"],
            "receipt_chain_changed": other["receipt_chain_sha256"] != live["receipt_chain_sha256"],
        }

    # The verdict changes only when a counterfactual changes committed symbols
    # or abstention.  Honest NULL otherwise.
    field_dependence = any(
        item["decision_changed"] or item["abstention_changed"] for item in comparisons.values()
    )
    if field_dependence:
        verdict = "FIELD_DEPENDENT"
        claim = (
            "at least one field-native counterfactual changed the committed output "
            "symbols or the abstention status of the canonical Qi field emit loop"
        )
    else:
        verdict = "NULL_NO_SYMBOL_OR_ABSTENTION_CHANGE"
        claim = (
            "the bounded field-native counterfactuals (zeroed field and scale-phase "
            "rotation) changed neither the committed symbols nor the abstention status"
        )

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "receipt_sha256": "",
        "model_id": MODEL_ID,
        "qi_config_fingerprint": qi_config.fingerprint,
        "codebook_fingerprint": controller.codebook_fingerprint,
        "messages": [dict(message) for message in messages],
        "max_output_symbols": max_output_symbols,
        "arms": list(arm_by_name.values()),
        "comparisons": comparisons,
        "field_dependence": field_dependence,
        "verdict": verdict,
        "claim": claim,
    }
    receipt["receipt_sha256"] = _sha256(
        _canonical({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    )
    _atomic_write(output, _canonical(receipt) + b"\n")
    return receipt


def _parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qi-config", type=Path, default=root / "cassi-qi-language.json")
    parser.add_argument("--output", type=Path, default=root / "_diag" / "qwen-displacement" / "qi-field-dependence.json")
    parser.add_argument("--max-output-symbols", type=int, default=16)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = measure_qi_field_dependence(
            qi_config_path=args.qi_config,
            output=args.output,
            max_output_symbols=args.max_output_symbols,
        )
    except (CassiFieldDependenceError, OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"field-dependence measurement failed: {error}") from error
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
