"""Generate and verify the final hash-linked Qi-native displacement receipt.

This runner deliberately has no native-Qwen dependency and no organism
dependency.  It loads the adopted canonical qi-config, starts from
``QiFieldController.initial_state`` (no trained checkpoint), performs the same
generation twice from the same fresh state, requires byte-for-byte deterministic
replay, round-trips the committed successor state through
``dump_state_bytes`` / ``load_state_bytes``, binds the frozen native baseline,
and compares the result with the offline native Qwen footprint receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_field_language import (
    CassiQiTextEngine,
    CassiQiTextResult,
    qi_state_sha256,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState
from cassi_qwen_displacement import (
    QI_NATIVE_DISPLACEMENT_SCHEMA,
    CassiQwenDisplacementError,
    build_qi_native_displacement_receipt,
    load_qwen_displacement_baseline,
    verify_displacement_receipt_hash,
)


class FinalDisplacementError(RuntimeError):
    """Raised when final displacement evidence is incomplete or inconsistent."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise FinalDisplacementError(f"evidence is not canonical JSON: {error}") from error


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FinalDisplacementError(f"could not read {path}: {error}") from error
    if not isinstance(value, Mapping):
        raise FinalDisplacementError(f"{path} must contain a JSON object")
    return value


def _self_hash(value: Mapping[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "receipt_sha256"}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _load_field_dependence(path: Path) -> tuple[bool, str, str]:
    value = _load_json(path)
    if value.get("schema") != "cassi.qi-field-dependence.v1":
        raise FinalDisplacementError("field-dependence receipt schema mismatch")
    claimed = value.get("receipt_sha256")
    if not isinstance(claimed, str) or len(claimed) != 64 or claimed != _self_hash(value):
        raise FinalDisplacementError("field-dependence receipt self-hash mismatch")
    dependence = value.get("field_dependence")
    if not isinstance(dependence, bool):
        raise FinalDisplacementError("field-dependence result must be a boolean")
    verdict = value.get("verdict")
    if not isinstance(verdict, str) or not verdict:
        raise FinalDisplacementError("field-dependence verdict is missing")
    return dependence, verdict, claimed


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise FinalDisplacementError(f"could not write {path}: {error}") from error


def _assert_replay(left: CassiQiTextResult, right: CassiQiTextResult) -> None:
    fields = (
        "prompt_symbols",
        "output_symbols",
        "output_bytes",
        "text",
        "receipt_sha256",
        "initial_state_sha256",
        "final_state_sha256",
    )
    mismatches = [name for name in fields if getattr(left, name) != getattr(right, name)]
    if mismatches:
        raise FinalDisplacementError(
            f"fresh deterministic replay changed: {', '.join(mismatches)}"
        )
    if not left.output_symbols:
        raise FinalDisplacementError("field-only generation committed no output symbols")
    if len(left.output_receipts) != len(left.output_symbols):
        raise FinalDisplacementError("not every committed output has an ownership receipt")


def build_final_evidence(args: argparse.Namespace) -> dict[str, Any]:
    qi_config = QiFieldConfig.from_dict(_load_json(args.qi_config))
    controller = QiFieldController(qi_config)
    engine = CassiQiTextEngine(controller, max_output_symbols=args.max_output_symbols)
    messages = ({"role": "user", "content": args.prompt},)

    def run_once() -> CassiQiTextResult:
        state = engine.initial_state(device="cpu")
        return engine.generate(
            state,
            messages,
            max_output_symbols=args.max_output_symbols,
        )

    first = run_once()
    replay = run_once()
    _assert_replay(first, replay)

    # Round-trip the committed successor state through dump/load and confirm the
    # state bytes restore to the exact same canonical hash the engine reported.
    dumped = controller.dump_state_bytes(first.state)
    reloaded = controller.load_state_bytes(dumped, device="cpu", dtype=torch.float32)
    reloaded_sha = qi_state_sha256(controller, reloaded)
    if not isinstance(reloaded, QiFieldState) or reloaded_sha != first.final_state_sha256:
        raise FinalDisplacementError(
            "dump/load state round-trip did not reproduce the committed final state"
        )

    # Continuations from the in-memory and reloaded copies of the same committed
    # state must be identical. Comparing with a fresh initial-state replay would
    # test a different causal state.
    expected_continuation = engine.generate(
        first.state,
        messages,
        max_output_symbols=args.max_output_symbols,
    )
    reloaded_continuation = engine.generate(
        reloaded,
        messages,
        max_output_symbols=args.max_output_symbols,
    )
    _assert_replay(expected_continuation, reloaded_continuation)

    baseline = load_qwen_displacement_baseline(args.baseline_receipt)
    field_dependence, dependence_verdict, dependence_hash = _load_field_dependence(
        args.field_dependence_receipt
    )
    receipt = build_qi_native_displacement_receipt(
        baseline=baseline,
        config_fingerprint=controller.config_fingerprint,
        codebook_fingerprint=controller.codebook_fingerprint,
        engine_fingerprint=engine.fingerprint,
        field_text_receipt_sha256=first.receipt_sha256,
        committed_output_count=len(first.output_symbols),
        field_dependence=field_dependence,
    )
    if receipt.get("schema") != QI_NATIVE_DISPLACEMENT_SCHEMA:
        raise FinalDisplacementError("final displacement receipt schema mismatch")
    serving_counts = receipt.get("qwen_serving", {}).get("counts")
    if not isinstance(serving_counts, Mapping) or any(
        isinstance(value, bool) or not isinstance(value, int) or value != 0
        for value in serving_counts.values()
    ):
        raise FinalDisplacementError("a live Qwen serving counter is nonzero or malformed")
    architecture = receipt.get("architecture")
    if not isinstance(architecture, Mapping):
        raise FinalDisplacementError("architecture counters are missing")
    if architecture.get("adaptive_persistent_tensor_count") != 1:
        raise FinalDisplacementError("adaptive_persistent_tensor_count is not one")
    for key in (
        "learned_parameter_count",
        "neural_layer_count",
        "optimizer_state_bytes",
        "engineered_feature_width",
    ):
        if architecture.get(key, 0) != 0:
            raise FinalDisplacementError(f"classical-ML counter {key} is nonzero")
    if architecture.get("probabilistic_sampler") is not False:
        raise FinalDisplacementError("probabilistic_sampler is not False")
    if architecture.get("state_layout") != "[S,9M,B]":
        raise FinalDisplacementError("state_layout is not the canonical Qi layout")
    verify_displacement_receipt_hash(receipt)
    completion = receipt.get("completion")
    if not isinstance(completion, Mapping) or not completion:
        raise FinalDisplacementError("completion ownership receipt is missing")
    if any(
        not isinstance(gate, Mapping) or gate.get("satisfied") is not True
        for gate in completion.values()
    ):
        raise FinalDisplacementError("a displacement completion gate is not satisfied")
    field_text = receipt.get("field_text")
    if not isinstance(field_text, Mapping):
        raise FinalDisplacementError("field-text receipt is missing")
    if field_text.get("committed_output_count") != len(first.output_symbols):
        raise FinalDisplacementError("committed output count is inconsistent")
    if field_text.get("receipt_sha256") != first.receipt_sha256:
        raise FinalDisplacementError("field-text receipt hash is inconsistent")
    if field_text.get("all_outputs_field_owned") is not True:
        raise FinalDisplacementError("not every committed output is field-owned")
    field_decision = receipt.get("field_decision")
    if not isinstance(field_decision, Mapping):
        raise FinalDisplacementError("field-decision receipt is missing")
    if field_decision.get("field_dependence") is not field_dependence:
        raise FinalDisplacementError("field-dependence result was not preserved")

    return {
        "schema": "cassi.qi-native-final-evidence.v1",
        "receipt_sha256": "",
        "displacement_receipt": receipt,
        "displacement_receipt_sha256": receipt["receipt_sha256"],
        "field_dependence_receipt_sha256": dependence_hash,
        "field_dependence_verdict": dependence_verdict,
        "model_id": "cassi-qi-language-v1",
        "deterministic_replay": {
            "passed": True,
            "output_symbols": list(first.output_symbols),
            "output_bytes_sha256": first.byte_sha256,
            "field_text_receipt_sha256": first.receipt_sha256,
            "final_state_sha256": first.final_state_sha256,
            "state_round_trip_sha256": reloaded_sha,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qi-config",
        type=Path,
        default=root / "cassi-qi-language.json",
    )
    parser.add_argument(
        "--baseline-receipt",
        type=Path,
        default=root / "_diag/qwen-displacement/baseline-receipt.json",
    )
    parser.add_argument(
        "--field-dependence-receipt",
        type=Path,
        default=root / "_diag/qwen-displacement/qi-field-dependence.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=root / "_diag/qwen-displacement/final-qi-native-evidence.json",
    )
    parser.add_argument("--prompt", default="Describe this field in one bounded turn.")
    parser.add_argument("--max-output-symbols", type=int, default=16)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    args = parse_args(argv)
    try:
        evidence = build_final_evidence(args)
        evidence["receipt_sha256"] = _self_hash(evidence)
        _atomic_write(args.out.resolve(), _canonical(evidence) + b"\n")
        displacement = evidence["displacement_receipt"]
        architecture = displacement["architecture"]
        print(
            json.dumps(
                {
                    "schema": evidence["schema"],
                    "receipt_sha256": evidence["receipt_sha256"],
                    "displacement_receipt_sha256": displacement["receipt_sha256"],
                    "field_dependence": displacement["field_decision"]["field_dependence"],
                    "field_dependence_verdict": evidence["field_dependence_verdict"],
                    "serving_counts": displacement["qwen_serving"]["counts"],
                    "architecture": architecture,
                    "model_id": evidence["model_id"],
                    "deterministic_replay": evidence["deterministic_replay"],
                    "path": str(args.out.resolve()),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (
        CassiQwenDisplacementError,
        FinalDisplacementError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        raise SystemExit(f"final displacement evidence failed: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())
