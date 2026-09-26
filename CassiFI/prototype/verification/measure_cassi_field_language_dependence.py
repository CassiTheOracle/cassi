"""Measure causal live-trajectory control of field-owned language emission.

Every arm loads the same trained ``QiFieldState`` checkpoint and runs the same
active boundary-port path. Counterfactual arms rotate only a seeded live
differential trajectory; the trained phase-coded circulation banks remain
bit-identical. A positive verdict requires a committed output-symbol change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from typing import Any, Final, Mapping, Sequence

import torch

from cassi_field_language import (
    CassiQiTextEngine,
    CassiQiTextResult,
    CassiQiTrajectoryLaw,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR


SCHEMA: Final[str] = "cassi.qi-field-dependence.v2"
MODEL_ID: Final[str] = "cassi-qi-corpus-language-v1"
_PHASE_ANGLES: Final[tuple[float, ...]] = (
    math.pi / 2.0,
    math.pi,
    3.0 * math.pi / 2.0,
)


class CassiFieldDependenceError(RuntimeError):
    """Raised when corpus-field counterfactual evidence is invalid."""


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
        raise CassiFieldDependenceError(
            f"value is not canonical finite JSON: {error}"
        ) from error


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_mapping(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CassiFieldDependenceError(f"could not load {label}: {error}") from error
    if not isinstance(value, Mapping):
        raise CassiFieldDependenceError(f"{label} must contain a JSON object")
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


def _phase_state(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    angle: float,
) -> QiFieldState:
    return law.rotate_live_context(state, angle)


def _arm(
    name: str,
    angle: float,
    text_result: CassiQiTextResult,
) -> dict[str, Any]:
    # Kept local to avoid broadening the live engine's public evidence surface.
    return {
        "name": name,
        "phase_angle_radians": angle,
        "initial_state_sha256": text_result.initial_state_sha256,
        "final_state_sha256": text_result.final_state_sha256,
        "corpus_memory_sha256": text_result.corpus_memory_sha256,
        "output_symbols": list(text_result.output_symbols),
        "output_symbols_sha256": _sha256(_canonical(list(text_result.output_symbols))),
        "output_bytes_sha256": text_result.byte_sha256,
        "text": text_result.text,
        "stop_reason": text_result.stop_reason,
        "committed_output_count": len(text_result.output_symbols),
        "field_text_receipt_sha256": text_result.receipt_sha256,
        "all_outputs_field_owned": text_result.all_outputs_field_owned,
    }


def _first_changed_position(left: tuple[int, ...], right: tuple[int, ...]) -> int | None:
    for index, (left_symbol, right_symbol) in enumerate(zip(left, right)):
        if left_symbol != right_symbol:
            return index
    return None if len(left) == len(right) else min(len(left), len(right))


def measure_qi_field_dependence(
    *,
    qi_config_path: Path,
    corpus_checkpoint_path: Path,
    output: Path,
    max_output_symbols: int = 32,
    messages: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, Any]:
    if isinstance(max_output_symbols, bool) or not 1 <= max_output_symbols <= 256:
        raise CassiFieldDependenceError("max_output_symbols must lie in [1, 256]")
    if messages is None:
        training = _load_mapping(
            corpus_checkpoint_path.parent / "training-receipt.json",
            "trajectory training receipt",
        )
        prompt = training["generation"]["training_examples"][0]["prompt"]
        messages = ({"role": "user", "content": str(prompt)},)
    if not messages:
        raise CassiFieldDependenceError("counterfactual messages cannot be empty")

    config = QiFieldConfig.from_dict(_load_mapping(qi_config_path, "Qi config"))
    controller = QiFieldController(config)
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=corpus_checkpoint_path,
        max_output_symbols=max_output_symbols,
    )
    initial = engine.initial_state(device="cpu")
    priming = engine.generate(initial, messages)
    if not priming.all_outputs_field_owned or not priming.output_symbols:
        raise CassiFieldDependenceError(
            "the priming trajectory did not commit field-owned output symbols"
        )
    probe_messages: tuple[dict[str, str], ...] = (
        {"role": "user", "content": "Continue"},
    )
    variants = [("live", 0.0, _phase_state(engine.law, priming.state, 0.0))] + [
        (f"phase_{index + 1}", angle, _phase_state(engine.law, priming.state, angle))
        for index, angle in enumerate(_PHASE_ANGLES)
    ]
    arms: list[dict[str, Any]] = []
    symbols_by_name: dict[str, tuple[int, ...]] = {}
    for name, angle, state in variants:
        result = engine.generate(state, probe_messages)
        if result.corpus_memory_sha256 != engine.corpus_memory_sha256:
            raise CassiFieldDependenceError(
                f"{name} changed the trained corpus memory"
            )
        if not result.all_outputs_field_owned or not result.output_symbols:
            raise CassiFieldDependenceError(
                f"{name} did not commit field-owned output symbols"
            )
        arms.append(_arm(name, angle, result))
        symbols_by_name[name] = result.output_symbols

    live_arm = arms[0]
    live_symbols = symbols_by_name["live"]
    comparisons: dict[str, dict[str, Any]] = {}
    for arm in arms[1:]:
        name = str(arm["name"])
        symbols = symbols_by_name[name]
        if arm["initial_state_sha256"] == live_arm["initial_state_sha256"]:
            raise CassiFieldDependenceError(
                f"{name} did not change the live Qi phase state"
            )
        if arm["corpus_memory_sha256"] != live_arm["corpus_memory_sha256"]:
            raise CassiFieldDependenceError(
                f"{name} changed the trained trajectory memory"
            )
        comparisons[name] = {
            "initial_state_changed": True,
            "trained_memory_unchanged": True,
            "decision_changed": symbols != live_symbols,
            "first_changed_position": _first_changed_position(live_symbols, symbols),
            "output_bytes_changed": arm["output_bytes_sha256"]
            != live_arm["output_bytes_sha256"],
            "final_state_changed": arm["final_state_sha256"]
            != live_arm["final_state_sha256"],
        }

    field_dependence = any(
        comparison["decision_changed"] for comparison in comparisons.values()
    )
    verdict = "FIELD_DEPENDENT" if field_dependence else "NULL_NO_SYMBOL_CHANGE"
    claim = (
        "a seeded live Qi trajectory rotation changed committed field-owned "
        "output symbols while trained phase-coded circulation remained bit-identical"
        if field_dependence
        else "the seeded live Qi trajectory rotations changed no committed symbol"
    )
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "receipt_sha256": "",
        "model_id": MODEL_ID,
        "qi_config_fingerprint": config.fingerprint,
        "codebook_fingerprint": controller.codebook_fingerprint,
        "engine_fingerprint": engine.fingerprint,
        "corpus_checkpoint_sha256": _sha256(corpus_checkpoint_path.read_bytes()),
        "corpus_memory_sha256": engine.corpus_memory_sha256,
        "priming_messages": [dict(message) for message in messages],
        "priming_output": priming.text,
        "probe_messages": [dict(message) for message in probe_messages],
        "max_output_symbols": max_output_symbols,
        "counterfactual": "seeded-live-trajectory-phase-rotation",
        "arms": arms,
        "comparisons": comparisons,
        "field_dependence": field_dependence,
        "verdict": verdict,
        "claim": claim,
    }
    receipt["receipt_sha256"] = _sha256(
        _canonical(
            {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        )
    )
    _atomic_write(output, _canonical(receipt) + b"\n")
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qi-config",
        type=Path,
        default=CONFIG_DIR / "cassi-qi-corpus-language.json",
    )
    parser.add_argument(
        "--corpus-checkpoint",
        type=Path,
        default=ARTIFACT_DIR / "cassi-qi-corpus-language" / "field-state.pt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_DIR / "qwen-displacement" / "qi-field-dependence.json",
    )
    parser.add_argument("--max-output-symbols", type=int, default=32)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    args = _parser().parse_args(argv)
    try:
        receipt = measure_qi_field_dependence(
            qi_config_path=args.qi_config,
            corpus_checkpoint_path=args.corpus_checkpoint,
            output=args.output,
            max_output_symbols=args.max_output_symbols,
        )
    except (CassiFieldDependenceError, OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"field-dependence measurement failed: {error}") from error
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
